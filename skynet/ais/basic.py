import math
import random

from .. import main
from .. import ai


class BasicNetwork(ai.AI):

    def issue_orders(self):
        orders = []
        orders.extend(self.issue_research_orders())
        orders.extend(self.issue_build_orders())
        orders.extend(self.issue_move_orders())
        return orders

    def issue_research_orders(self):
        orders = []
        for i in main.RESEARCH:
            insight = math.floor(self.network.insight / 3 * 1000) / 1000
            orders.append(main.ResearchOrder(i, insight))
        return orders

    def issue_build_orders(self):
        orders = []
        field_number = len(self.network.fields)
        for field in self.network.fields:
            for resource, (color1, color2) in main.COLOR_MATCHES.items():
                value1 = math.floor(getattr(self.network, color1) / 2 / field_number * 1000) / 1000
                value2 = math.floor(getattr(self.network, color2) / 2 / field_number * 1000) / 1000
                money = math.floor(self.network.money / 3 / field_number * 1000) / 1000
                orders.append(main.BuildOrder(field.coordinates, resource, money, value1, value2))
        return orders

    def issue_move_orders(self):
        orders = []
        for field in self.network.fields:
            military = field.military
            target = field.get_nearest_field(lambda x: x.network is None or x.network.name != self.network.name)
            if target:
                move = field + target.board.get_direction(field.coordinates, target.coordinates)
                orders.append(main.MoveOrder(military / 2, field.coordinates, move.coordinates))
        return orders





