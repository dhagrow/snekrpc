# Basic service/server example.

import snekrpc


class EchoService(snekrpc.Service, name='echo'):
    @snekrpc.command()
    def echo(self, value: str) -> str:
        return value


server = snekrpc.Server()
server.add_service(EchoService())
server.serve()
