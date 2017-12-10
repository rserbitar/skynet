# interface

# ['build', (1,1), 'commerce', 0, 0, 0]
# ['research', 'production', 0]
# ['request_trade', None, 100, 'insight', None, None]
# ['accept_trade', 1234, 100, 'red']
# ['cancel_trade', 1234]
# ['send', 'empire1', 100, 'money', 12345]
# ['move', 100, (1,1), (2,1)]
# ['propose_alliance', '1']
# ['accept_alliance', '2']
# ['cancel_alliance', '2']


import collections
import logging
import random
import math
import itertools
import statistics
import copy

import holoviews


logger = logging.getLogger()

COLORS = ['yellow', 'orange', 'red', 'purple', 'blue', 'green']
RESOURCES = ['yellow', 'orange', 'red', 'purple', 'blue', 'green', 'money', 'insight']
IMMOVABLES = ['commerce', 'industry', 'research']
COLOR_MATCHES = {IMMOVABLES[0]: COLORS[0:2],
                 IMMOVABLES[1]: COLORS[2:4],
                 IMMOVABLES[2]: COLORS[4:6]}
FIELD_STATS = COLORS + IMMOVABLES + ['military']
RESEARCH = ['intelligence', 'power', 'production']

FIELDS_PER_EMPIRE = 100
MIN_START_DIST = FIELDS_PER_EMPIRE ** 0.5 / 1.5
MAX_COLOR_STDDEV = 4.5
STARTING_MONEY = 100


def normpdf(x, mu, sigma):
    u = (x - mu) / sigma
    y = (1 / (math.sqrt(2 * math.pi) * sigma ** 2)) * math.exp(-u * u / 2)
    return y


class TradeRequest:

    def __init__(self, id, requester, requested_ammount, requested_kind,
                 tradepartner=None, offered_ammount=None, offered_kind=None):
        self.id = id
        self.requester = requester
        self.tradepartner = tradepartner
        self.requested_ammount = requested_ammount
        self.requested_kind = requested_kind if requested_kind in RESOURCES else None
        self.offered_ammount = offered_ammount
        self.offered_kind = offered_kind if offered_kind in RESOURCES else None
        self.confirmed_tradepartner = False
        self.confirmed_requester = False
        self.requester_executed = False
        self.tradepartner_executed = False
        self.cancelled = False


class Network:

    def __init__(self, name, ai):
        self.name = name
        self.color = 'black'
        self.yellow = 0
        self.orange = 0
        self.red = 0
        self.purple = 0
        self.blue = 0
        self.green = 0
        self.money = STARTING_MONEY
        self.insight = 0

        self.production_brut = 0
        self.intelligence_brut = 0
        self.power_brut = 0

        self.fields = []
        self.ai = ai

    @property
    def production(self):
        return self._research_func(self.production_brut)

    @property
    def intelligence(self):
        return self._research_func(self.intelligence_brut)

    @property
    def power(self):
        return self._research_func(self.power_brut)

    @staticmethod
    def _research_func(value):
        return 1 + math.log(1 + value / 1000) / math.log(2)

    def request_resource(self, resource, ammount):
        return sorted([0, ammount, getattr(self, resource, 0)])[1]

    def add_resource(self, resource, ammount):
        setattr(self, resource, getattr(self, resource, 0) + ammount)

    def log_status(self):
        logger.info("Network '{}'".format(self.name))
        for attribute in RESOURCES + ['production', 'intelligence', 'power']:
            logger.info("{}: {}".format(attribute.upper(), getattr(self, attribute)))
        logger.info("FIELDS: {}".format([i.coordinates for i in self.fields]))
        logger.info('')

    def research(self, subject, insight):
        insight = self.request_resource('insight', insight)
        if subject in RESEARCH and insight:
            self.add_resource(subject + '_brut', insight)
            self.insight -= insight
            new_value = getattr(self, subject)
            logger.info("Network '{}' is researching {} to {} for {} insight.".format(self.name,
                                                                                      subject,
                                                                                      new_value,
                                                                                      insight))

    def issue_orders(self, game, name):
        logger.info("Network '{}' issueing orders.".format(name))
        orders = self.ai(game, name).issue_orders()
        return orders


class Field:

    def __init__(self, board, coordinates):
        self.board = board
        self.coordinates = coordinates

        self.yellow = 0
        self.orange = 0
        self.red = 0
        self.purple = 0
        self.blue = 0
        self.green = 0

        self.commerce_brut = 0
        self.research_brut = 0
        self.industry_brut = 0

        self.military = 0

        self.network = None
        self.moved_military = collections.defaultdict(float)

    def __sub__(self, b):
        result = None
        if isinstance(b, Field) or isinstance(b, tuple):
            result = self.distance(b)
        return result

    @property
    def commerce(self):
        return self._immovable_func(self.commerce_brut)

    @property
    def industry(self):
        return self._immovable_func(self.industry_brut)

    @property
    def research(self):
        return self._immovable_func(self.research_brut)

    @staticmethod
    def _immovable_func(value):
        return value ** 0.5

    def add_resource(self, resource, ammount):
        setattr(self, resource, getattr(self, resource, 0) + ammount)

    def distance(self, b):
        if isinstance(b, Field):
            b = b.coordinates
        return self.board.distance(self.coordinates, b)

    def generate_money(self):
        if self.network:
            money = self.commerce * self.network.production
            logger.debug('Field {} generated {} money for {}.'.format(self.coordinates, money, self.network.name))
            self.network.money += money

    def generate_colors(self):
        if self.network:
            self.network.yellow += self.yellow
            self.network.orange += self.orange
            self.network.red += self.red
            self.network.purple += self.purple
            self.network.blue += self.blue
            self.network.green += self.green
            logger.debug('Field {} generated {} resources for {}.'.format(self.coordinates, (self.yellow,
                                                                                             self.orange,
                                                                                             self.red,
                                                                                             self.purple,
                                                                                             self.blue,
                                                                                             self.green),
                                                                          self.network.name))

    def generate_military(self):
        if self.network:
            military = self.industry * self.network.power
            logger.debug('Field {} generated {} military for {}.'.format(self.coordinates, military, self.network.name))
            self.military += military

    def generate_insight(self):
        if self.network:
            insight = self.research * self.network.intelligence
            logger.debug('Field {} generated {} insight for {}.'.format(self.coordinates, insight, self.network.name))
            self.network.insight += insight

    def build(self, resource, money, color1, color2):
        if resource in IMMOVABLES:
            colorname1, colorname2 = COLOR_MATCHES[resource]
            money = self.network.request_resource('money', money)
            color1 = self.network.request_resource(colorname1, color1)
            color2 = self.network.request_resource(colorname2, color2)
            increase = ((1 + color1) * (1 + color2)) ** 0.5 * money
            self.add_resource(resource + '_brut', increase)
            self.network.add_resource(colorname1, -color1)
            self.network.add_resource(colorname2, -color2)
            self.network.money -= money
            new_value = getattr(self, resource)
            logstring = "Network '{}' built {} to {} for {} money and {} resources on field {}."
            logger.info(logstring.format(self.network.name, resource, new_value, money, (color1, color2),
                                         self.coordinates))


class Board:
    def __init__(self, size, game):
        self.game = game
        self.size = size
        self.fields = []
        for i in range(self.size[0]):
            for j in range(self.size[1]):
                self.fields.append(Field(self, (i, j)))
        self.field_dict = {field.coordinates: field for field in self.fields}
        diameter = (self.size[0] ** 2 + self.size[1] ** 2) ** 0.5
        sigma1 = diameter / 20
        sigma2 = sigma1 * 1.5
        peak1 = 10
        peak2 = 3
        count1 = int(diameter / 10)
        count2 = int(diameter / 8)
        stddev = MAX_COLOR_STDDEV + 1
        while stddev > MAX_COLOR_STDDEV:
            for color in COLORS:
                self.reset_color(color)
                for i in range(count1):
                    self.seed_colors(peak1, sigma1, color)
                for i in range(count2):
                    self.seed_colors(peak2, sigma2, color)
            data = [[sum([getattr(self.field_dict[(i, j)], field_stat)
                          for field_stat in COLORS])
                     for j in range(self.size[1])]
                    for i in range(self.size[0])]
            stddev = (statistics.stdev(itertools.chain(*data)))

    def reset_color(self, color):
        for field in self.fields:
            setattr(field, color, 0)

    def seed_colors(self, peak, std, color):
        x = random.randint(0, self.size[0] - 1)
        y = random.randint(0, self.size[1] - 1)
        for field in self.fields:
            distance = field - (x, y)
            value = normpdf(distance, 0, std) / normpdf(0, 0, std) * peak + getattr(field, color)
            setattr(field, color, value)

    def distance(self, coordinates_a, coordinates_b):
        x_dif = abs(coordinates_a[0] - coordinates_b[0])
        y_dif = abs(coordinates_a[1] - coordinates_b[1])
        x = min(x_dif, abs(x_dif - self.size[0]))
        y = min(y_dif, abs(y_dif - self.size[1]))
        return (x ** 2 + y ** 2) ** 0.5

    def plot_field_stats(self, field_stats):
        if not isinstance(field_stats, list):
            field_stats = [field_stats]
        data = collections.defaultdict(list)
        all_stats = FIELD_STATS[:]
        all_stats.remove(field_stats[0])
        all_stats = field_stats + all_stats
        for field in self.fields:
            data['x'].append(field.coordinates[0])
            data['y'].append(field.coordinates[1])
            for i in all_stats:
                data[i].append(getattr(field, i))
        table = holoviews.Table(data, kdims=['x', 'y'], vdims=all_stats)
        heatmap = holoviews.HeatMap(table).opts(style={'cmap': 'inferno'})
        return heatmap

    def plot_field_stat(self, field_stat):
        data = collections.defaultdict(list)
        for field in self.fields:
            data['x'].append(field.coordinates[0])
            data['y'].append(field.coordinates[1])
            data[field_stat].append(getattr(field, field_stat))
        table = holoviews.Table(data, kdims=['x', 'y'], vdims=[field_stat])
        heatmap = holoviews.HeatMap(table).opts(style={'cmap': 'inferno'})
        return heatmap

    def plot_networks(self):
        table = self.get_networks_table()
        heatmap = holoviews.HeatMap(table).opts(style={'cmap': 'tab10'})
        return heatmap

    def get_networks_table(self):
        data = collections.defaultdict(list)
        for field in self.fields:
            data['x'].append(field.coordinates[0])
            data['y'].append(field.coordinates[1])
            data['network'].append(field.network.name if field.network else None)
        table = holoviews.Table(data, kdims=['x', 'y'], vdims=['network'])
        return table

    def plot_overview(self):
        networks = self.plot_networks().opts(plot={'colorbar': False})
        fields = self.plot_field_stat('industry') + self.plot_field_stat('research') + self.plot_field_stat(
            'commerce') + self.plot_field_stat('military')
        return (networks + fields).cols(3)


class Game:
    def __init__(self, networks):
        self.networks = networks
        self.network_dict = {network.name: network for network in self.networks}
        size = int(len(networks) ** 0.5 * FIELDS_PER_EMPIRE ** 0.5)
        self.board = Board((size, size), self)
        self.turn = 0
        self.orders = {}
        self.trade_requests = []
        self.trade_request_dict = {trade.id: trade for trade in self.trade_requests}
        self.alliances = []
        self.trade_counter = 0
        self.place_networks()

    def place_networks(self):
        distances = [0]
        locations = []
        while min(distances) < MIN_START_DIST:
            distances, locations = [], []
            for network in self.networks:
                x, y = random.randint(0, self.board.size[0] - 1), random.randint(0, self.board.size[1] - 1)
                locations.append([network, (x, y)])
            for location in locations:
                for location2 in locations:
                    if location[0] != location2[0]:
                        distances.append(self.board.distance(location[1], location2[1]))

        for network, coordinates in locations:
            self.board.field_dict[coordinates].network = network
            logger.info("Network '{}' starts at {}.".format(network.name, coordinates))

    def do_turn(self):
        logger.info('Starting turn {}.'.format(self.turn))
        self.calculate_network_fields()
        self.clear_orders()
        self.get_orders()
        self.process_move_orders()
        self.resolve_combat()
        self.calculate_network_fields()
        self.resolve_trade_orders()
        self.generate_stuff()
        self.process_build_orders()
        self.process_research_orders()
        self.wrap_up_turn()
        self.turn += 1

    def wrap_up_turn(self):
        for network in self.networks:
            network.log_status()

    def calculate_network_fields(self):
        for network in self.networks:
            network.fields = []
            for field in self.board.fields:
                if field.network == network:
                    network.fields += [field]
            logging.info("Network '{}' has {} fields.".format(network.name, len(network.fields)))

    def clear_orders(self):
        logger.info('Clearing orders.')
        self.orders = {}

    def get_orders(self):
        logger.info('Getting orders.')
        orders = {}
        for network in self.networks:
            try:
                orders[network] = network.issue_orders(copy.deepcopy(self), network.name)
            except:
                logger.info("Network '{}' failed to generate orders for turn {}".format(network.name, self.turn))
        self.orders = orders

    def resolve_trade_orders(self):
        logger.info('Resolving trade orders.')
        for sender, orders in self.orders.items():
            for order in orders:
                try:
                    trade_dict = {'request_trade': self.resolve_request_trade,
                                  'accept_trade': self.resolve_accept_trade,
                                  'cancel_trade': self.resolve_cancel_trade,
                                  'send': self.resolve_send}
                    trade_dict[order[0]](order, sender)
                except:
                    pass

    def resolve_request_trade(self, order, sender):
        trade_id = self.trade_counter
        self.trade_counter += 1
        tradepartner = None
        if order[1]:
            tradepartner = self.network_dict.get(order[1])
        trade = TradeRequest(trade_id, sender, order[2], order[3], tradepartner, order[4], order[5])
        self.trade_request_dict[trade_id] = trade
        logstring = "Network '{}' requested trade of {} {}".format(trade.requester.name,
                                                                   trade.requested_ammount,
                                                                   trade.requested_kind)
        if trade.tradepartner:
            logstring += " from network '{}".format(trade.tradepartner.name)
        if trade.offered_kind and trade.offered_ammount:
            logstring += ' for {} {}'.format(trade.offered_ammount, trade.offered_kind)
        logging.info(logstring + '.()'.format(trade.id))

    def resolve_accept_trade(self, order, sender):
        trade = self.trade_request_dict.get(order[1])
        if trade:
            logstring = "Network '{}' accepted trade {}".format(sender.name, trade.id)
            if trade.offered_ammount is None and order[2]:
                trade.offered_ammount = order[2]
            if trade.offered_tkind is None and order[3]:
                trade.offered_kind = order[3]
                logstring += ' for {} {}'.format(trade.offered_ammount, trade.offered_kind)
            if sender == trade.requester:
                trade.confirmed_requester = trade
            if sender == trade.tradepartner:
                trade.confirmed_tradepartner = trade
            logging.info(logstring + '.')

    def resolve_cancel_trade(self, order, sender):
        trade = self.trade_request_dict.get(order[1])
        if trade:
            if sender == trade.requester:
                trade.cancelled = True
                logging.info("Network '{}' cancelled trade request {}".format(sender.name, trade.id))
            elif sender == trade.tradepartner:
                trade.confirmed_tradepartner = False
                logging.info("Network '{}' stepped down from trade {}".format(sender.name, trade.id))

    def resolve_send(self, order, sender):
        receiver, ammount, kind, trade = order[1:]
        receiver = self.network_dict.get(receiver)
        trade = self.trade_request_dict.get(trade)
        if kind in RESOURCES:
            sender_value = getattr(sender, kind) - ammount
            if sender_value >= 0 and receiver:
                receiver_value = getattr(receiver, kind) + ammount
                setattr(sender, kind, sender_value)
                setattr(receiver, kind, receiver_value)
                logging.info(
                    "Network '{}' sent {} {} to network '{}'".format(sender.name, ammount, kind, receiver.name))
                if trade:
                    if sender.name == trade.requester:
                        trade.requester_executed = True
                        logging.info("Network '{}' fulfilled trade {} as requester.".format(sender.name, trade.id))
                    if sender.name == trade.tradepartner:
                        trade.tradepartner_executed = True
                        logging.info("Network '{}' fulfilled trade {} as tradepartner.".format(sender.name, trade.id))

    def process_move_orders(self):
        logger.info('Processing move orders.')
        for mover, orders in self.orders.items():
            for order in orders:
                #                try:
                if order[0] == 'move':
                    military, field, target = order[1:]
                    field = self.board.field_dict.get(tuple(field))
                    target = self.board.field_dict.get(tuple(target))
                    military = sorted([0, military, field.military])[1]
                    distance = field.distance(target)
                    if field.network == mover and distance <= 1 and military:
                        target.moved_military[mover] += military
                        field.military -= military
                        logger.info("Network '{}' moved {} military from {} to {}.".format(mover.name,
                                                                                           military,
                                                                                           field.coordinates,
                                                                                           target.coordinates))

    #                except:
    #                    pass

    def resolve_combat(self):
        logger.info('Resolving combat.')
        for field in self.board.fields:
            if field.moved_military:
                field.moved_military[field.network] += field.military
                troops = list(field.moved_military.items())
                troops = sorted(troops, key=lambda x: x[1], reverse=True)
                if len(troops) > 1:
                    winner = troops[0]
                    runner_up = troops[1]
                    field.military = winner[1] - runner_up[1]
                    if winner[1] > runner_up[1]:
                        field.network = winner[0]

                    divider = 1 + runner_up[1] / winner[1]

                    field.industry_brut /= divider
                    field.research_brut /= divider
                    field.commerce_brut /= divider

                    logger.info("Network '{}' won combat in field {}.".format(winner[0].name, field.coordinates))
                    if troops[1][0]:
                        logger.info("Network '{}' lost {} military in combat, remaining {}.".format(winner[0].name,
                                                                                                    runner_up[1],
                                                                                                    field.military))
                        for troop in troops[1:]:
                            logger.info(
                                "Network '{}' lost {} military in combat.".format(troop[0].name if troop[0] else None,
                                                                                  troop[1]))
                        for i in IMMOVABLES:
                            loss = getattr(field, i)
                            if loss:
                                logger.info('{} money worth of {} was destroyed.'.format(loss * divider - loss, i))
                else:
                    field.military = troops[0][1]
                field.moved_military = collections.defaultdict(float)

    def process_build_orders(self):
        logger.info('Processing build orders.')
        for builder, orders in self.orders.items():
            for order in orders:
                #                try:
                if order[0] == 'build':
                    field, kind, money, resource1, resource2 = order[1:]
                    field = self.board.field_dict[field]
                    if field.network == builder:
                        field.build(kind, money, resource1, resource2)

    #                except:
    #                    pass

    def generate_stuff(self):
        logger.info('Generating stuff.')
        for field in self.board.fields:
            field.generate_money()
            field.generate_military()
            field.generate_insight()
        for field in self.board.fields:
            field.generate_colors()

    def process_research_orders(self):
        logger.info('Processing research orders.')
        for researcher, orders in self.orders.items():
            for order in orders:
                try:
                    if order[0] == 'research':
                        subject, insight = order[1:]
                        researcher.research(subject, insight)
                except:
                    pass