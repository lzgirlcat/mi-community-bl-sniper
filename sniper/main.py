from string import ascii_lowercase

from rich.console import Console
from ntplib import NTPClient
from pytz import timezone
from datetime import datetime, timedelta
from time import sleep
from sniper.api import Client
from threading import Thread
from random import choice

from .utils import get_cookies, TimeOffsetManager

CN_NTP_SERVERS = [
    "ntp.tencent.com",  # Tencent Cloud
    "cn.pool.ntp.org",  # China NTP Pool
]

UTC = timezone("UTC")
BEIJING_TZ = timezone("Asia/Shanghai")


# used for debugging, do not edit !
TD_DAYS = 1
FIRE_AT = {
    # "hour": 23,
    # "minute": 48,
    # "second": 00
}


def main(use_ntp: bool, browsers: list[str] = ["firefox", "thorium"], tokens: list[str] = []):
    console = Console()

    for browser in browsers:
        console.print(f"[green]loading tokens for[/green]:[underline] {browser}[/underline]")

        cookies = get_cookies(browser)
        if cookies and (token:=cookies.get("new_bbs_serviceToken")):
            tokens.append(token)
        else:
            console.print(f"[red]failed to load cookies from: [underline]{browser}[/underline][/red]")
    if not tokens:
        console.print("[red bold]failed to load any tokens, exiting...")
        return

    console.print(f"tokens: {tokens}")

    if use_ntp:
        console.print(f"[yellow]updating NTP time...[/yellow]")
        NTP_client = NTPClient()

        offset = None
        for _ in CN_NTP_SERVERS:
            server = choice(CN_NTP_SERVERS)
            try:
                resp = NTP_client.request(server)
            except:
                continue
            else:
                ntp_time = datetime.fromtimestamp(resp.tx_time, timezone("UTC"))
                break

        if ntp_time is None:
            console.print("[red bold]failed to set ntp time:<[/red bold]")
            return

        offset = TimeOffsetManager(ntp_time)
        beijing_time = ntp_time.astimezone(BEIJING_TZ)

        console.print(f"it is [underline bold]{beijing_time.strftime("%Y-%m-%d %H:%M:%S.%f")}[/underline bold] in Beijing right now")
    else:
        console.print(f"[red]running [underline bold]without NTP[/underline bold]![/red]")
        beijing_time = datetime.now(tz=BEIJING_TZ)
        offset = TimeOffsetManager(datetime.now())

    console.print(f"current system time: {datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")}")
    console.print(f"current offset time: {offset.time.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")}")
    diff = abs((datetime.now(UTC) - offset.time.astimezone(UTC)).total_seconds())
    console.print(f"difference: {diff}")

    client = Client(tokens[0])
    status = client.check_status()
    first_offset, http_offset, probed_offset = client.measure_offsets()

    if status["is_pass"] == 1:
        console.print("[green bold]unlock request already granted, exiting...")
        return
    elif status["button_state"] == 2:
        console.print(f"[red bold]unlock status check ratelimited to {status["deadline_format"]} :<, exiting...[/red bold]")
        return
    elif status["button_state"] == 3:
        console.print("[red bold]account too young to apply for unlock!, exiting...[/red bold]")
        return
    elif status["button_state"] == 1:
        console.print("[blue bold]unlock request possible, continuing...")

    offsets = [
        -0.1, 0,
    ]

    if abs(first_offset - probed_offset) > 0.05:
        offsets.append(first_offset)
        offsets.append(probed_offset)
    else:
        offsets.append(min(first_offset, probed_offset))

    workers: list[Thread] = []
    for n, delta in enumerate(offsets):
        workers.append(
            Thread(
                target=worker, args=(
                    console,
                    ascii_lowercase[n],
                    choice(tokens),
                    beijing_time,
                    offset,
                    delta
                )
            )
        )

    for i in workers:
        i.start()

    for i in workers:
        i.join()


def worker(
    console: Console,
    id: str,
    token: str,
    beijing_time: datetime,
    offset: TimeOffsetManager,
    fire_delta: float = 0,
):
    client = Client(token)
    target = (beijing_time + timedelta(days=TD_DAYS)).replace(
        **{"hour":0, "minute":0, "second":0, "microsecond":0, **FIRE_AT} # type: ignore
    ) - timedelta(seconds=fire_delta)
    console.print(f"[yellow underline bold]{id}[/yellow underline bold] firing at {target.strftime("%Y-%m-%d %H:%M:%S.%f")}")
    while True:
        if (diff := (target - offset.time).total_seconds()) > 5:
            sleep(min(3, diff - 1))
        elif diff < 0:
            console.print(f"[yellow underline bold]{id}[/yellow underline bold]: -{fire_delta} firing !!!")
            res = client.try_apply()
            console.print(f"[yellow underline bold]{id}[/yellow underline bold]: {res}")
            if res["code"] == 0:
                if res["apply_result"] == 1:
                    console.print(f"[yellow underline bold]{id}[/yellow underline bold]: [green bold]success!!!!!![/green bold]")
                if res["apply_result"] == 6:
                    console.print(f"[yellow underline bold]{id}[/yellow underline bold]: [green bold]the request might've succeeded, please check MI Unlock[/green bold]")
                elif res["apply_result"] == 3:
                    console.print(f"[yellow underline bold]{id}[/yellow underline bold]: [red bold]limit reached:<[/red bold]")
                    console.print(f"[yellow underline bold]{id}[/yellow underline bold]: try again later at {res["deadline_format"]}")
                elif res["apply_result"] == 4:
                    console.print(f"[yellow underline bold]{id}[/yellow underline bold]: [red bold]ratelimited until {res["deadline_format"]}[/red bold]")
            elif res["code"] == 100001:
                console.print(f"[yellow underline bold]{id}[/yellow underline bold]: [red bold]request was rejected !?![/red bold]")
            elif res["code"] == 100003:
                console.print(f"[yellow underline bold]{id}[/yellow underline bold]: [blue bold]unknown!?! checking status...[/blue bold]")
                status = client.check_status()
                if status["is_pass"] == 1:
                    console.print(f"[yellow underline bold]{id}[/yellow underline bold]: [green bold]success!!!!!![/green bold]")
            break
        else:
            sleep(0.0001)
