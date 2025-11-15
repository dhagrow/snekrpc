from snekrpc import cli


def main():
    try:
        cli.main()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
