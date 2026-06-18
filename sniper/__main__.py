from .main import main


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument(
        "--no-ntp",
        help="dont use NTP",
        dest="ntp",
        action="store_false",
        default=True,
    )
    parser.add_argument(
        "--no-",
        help="dont use NTP",
        action="store_false",
        default=True,
    )
    parser.add_argument(
        "browsers", help="The browsers from which the script should extract tokens", action="extend", nargs="+", type=str
    )
    args = parser.parse_args()

    main(args.ntp, args.browsers)
