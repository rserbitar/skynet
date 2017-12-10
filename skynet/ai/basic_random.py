import math
import random

import skynet

class BasicRandomNetwork():

    def __init__(self, game, name):
        self.name = name
        self.game = game
        self.network = game.network_dict[self.name]

    def issue_orders(self):
        orders = []
        orders.extend(self.issue_research_orders())
        orders.extend(self.issue_build_orders())
        orders.extend(self.issue_move_orders())
        return orders

    def issue_research_orders(self):
        orders = []
        insight = self.network.insight
        for i in skynet.skynet.RESEARCH:
            insight = math.floor(self.network.insight / 3 * 1000) / 1000
            orders.append(['research', i, insight])
        return orders

    def issue_build_orders(self):
        orders = []
        field_number = len(self.network.fields)
        for field in self.network.fields:
            for resource, (color1, color2) in skynet.skynet.COLOR_MATCHES.items():
                value1 = math.floor(getattr(self.network, color1) / 2 / field_number * 1000) / 1000
                value2 = math.floor(getattr(self.network, color2) / 2 / field_number * 1000) / 1000
                money = math.floor(self.network.money / 3 / field_number * 1000) / 1000
                orders.append(['build', field.coordinates, resource, money, value1, value2])
        return orders

    def issue_move_orders(self):
        orders = []
        for field in self.network.fields:
            military = field.military
            move = random.choice([(0, 1), (0, -1), (-1, 0), (1, 0)])
            target = [field.coordinates[0] + move[0], field.coordinates[1] + move[1]]
            for i, value in enumerate(target):
                if value < 0:
                    target[i] = self.game.board.size[i] - 1
                if value >= self.game.board.size[i]:
                    target[i] = 0
            orders.append(['move', military / 2, field.coordinates, target])
        return orders