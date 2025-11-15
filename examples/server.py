import snekrpc
from snekrpc import logs

class Service(snekrpc.Service):
    @snekrpc.command()
    def echo(self, value):
        return value

def main():
    logs.init()

    s = snekrpc.Server('tcp://localhost:1234')
    s.add_service(Service(), alias='ex')
    s.serve()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
