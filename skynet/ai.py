import abc
import typing

if False:
    from . import main


class AI(abc.ABC):

    def __init__(self, game: 'main.Game', name: str) -> None:
        self.name = name
        self.game = game
        self.network = game.network_dict[self.name]

    @abc.abstractmethod
    def issue_orders(self) -> typing.List[typing.NamedTuple]:
        pass
