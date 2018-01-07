# interface

import collections
import logging
import random
import math
import itertools
import statistics
import copy
import typing
import traceback
import sys
import functools

import holoviews
import holoviews.streams
import pandas

from . import ai


class BuildOrder(typing.NamedTuple):
    field: 'Coordinates'
    resource: str
    money: float
    color1: float
    color2: float


class ResearchOrder(typing.NamedTuple):
    subject: str
    insight: float


class MoveOrder(typing.NamedTuple):
    military: float
    field: 'Coordinates'
    target: 'Coordinates'


class RequestTradeOrder(typing.NamedTuple):
    tradepartner: typing.Optional[str]
    request_amount: float
    request_good: str
    offered_amount: typing.Optional[float]
    offered_good: typing.Optional[str]


class AcceptTradeOrder(typing.NamedTuple):
    trade_id: int
    offered_amount: float
    offered_good: str


class CancelTradeOrder(typing.NamedTuple):
    trade_id: int


class SendOrder(typing.NamedTuple):
    receiver: str
    amount: float
    good: str
    trade_id: int


logger = logging.getLogger()


COLORS = ['yellow', 'orange', 'red', 'purple', 'blue', 'green']
RESOURCES = ['yellow', 'orange', 'red', 'purple', 'blue', 'green', 'money', 'insight']
IMMOVABLES = ['commerce', 'industry', 'research']
MUTABLE_FIELD_STATS = IMMOVABLES + ['military']
COLOR_MATCHES = {IMMOVABLES[0]: COLORS[0:2],
                 IMMOVABLES[1]: COLORS[2:4],
                 IMMOVABLES[2]: COLORS[4:6]}
FIELD_STATS = COLORS + IMMOVABLES + ['military']
RESEARCH = ['intelligence', 'power', 'production']

FIELDS_PER_EMPIRE = 100
MIN_START_DIST = FIELDS_PER_EMPIRE ** 0.5 / 1.5
MAX_COLOR_STDDEV = 4.5
STARTING_MONEY = 100.


class Coordinates(typing.NamedTuple):
    x: int
    y: int


class Network:

    def __init__(self, name: str, ai: typing.Type['ai.AI']) -> None:
        self.name = name
        self.color = 'black'
        self.yellow = 0.
        self.orange = 0.
        self.red = 0.
        self.purple = 0.
        self.blue = 0.
        self.green = 0.
        self.money = STARTING_MONEY
        self.insight = 0.

        self.production_brut = 0.
        self.intelligence_brut = 0.
        self.power_brut = 0.

        self.fields: typing.List['Field'] = []
        self.ai = ai

    @property
    def production(self) -> float:
        return self._research_func(self.production_brut)

    @property
    def intelligence(self) -> float:
        return self._research_func(self.intelligence_brut)

    @property
    def power(self) -> float:
        return self._research_func(self.power_brut)

    @staticmethod
    def _research_func(value: float) -> float:
        return 1 + math.log(1 + value / 1000) / math.log(2)

    def request_resource(self, resource: str, amount: float) -> float:
        return sorted([0, amount, getattr(self, resource, 0)])[1]

    def add_resource(self, resource: str, amount: float) -> None:
        setattr(self, resource, getattr(self, resource, 0) + amount)

    def log_status(self) -> None:
        logger.info("Network '{}'".format(self.name))
        for attribute in RESOURCES + ['production', 'intelligence', 'power']:
            logger.info("{}: {}".format(attribute.upper(), getattr(self, attribute)))
        logger.info("FIELDS: {}".format([i.coordinates for i in self.fields]))
        logger.info('')

    def research(self, subject: str, insight: float) -> None:
        insight = self.request_resource('insight', insight)
        if subject in RESEARCH and insight:
            self.add_resource(subject + '_brut', insight)
            self.insight -= insight
            new_value = getattr(self, subject)
            logger.info("Network '{}' is researching {} to {} for {} insight.".format(self.name,
                                                                                      subject,
                                                                                      new_value,
                                                                                      insight))

    def issue_orders(self, game: 'Game', name: str) -> typing.List[typing.NamedTuple]:
        logger.info("Network '{}' issueing orders.".format(name))
        ai = self.ai(game, name)
        orders = ai.issue_orders()
        return orders


class Field:

    def __init__(self, board: 'Board', coordinates: Coordinates) -> None:
        self.board = board
        self.coordinates = coordinates

        self.yellow = 0.
        self.orange = 0.
        self.red = 0.
        self.purple = 0.
        self.blue = 0.
        self.green = 0.

        self.commerce_brut = 0.
        self.research_brut = 0.
        self.industry_brut = 0.

        self.military = 0.

        self.network: Network = None
        self.moved_military: typing.Dict[Network, float] = collections.defaultdict(float)

    def __sub__(self, b: typing.Union['Field', Coordinates]) -> float:
        result = None
        if isinstance(b, Field) or isinstance(b, Coordinates):
            result = self.distance(b)
        return result

    def __add__(self, b: Coordinates) -> 'Field':
        result = None
        if isinstance(b, Coordinates):
            result = self.add_coordinates(b)
        return result

    @property
    def commerce(self) -> float:
        return self._immovable_func(self.commerce_brut)

    @property
    def industry(self) -> float:
        return self._immovable_func(self.industry_brut)

    @property
    def research(self) -> float:
        return self._immovable_func(self.research_brut)

    @staticmethod
    def _immovable_func(value: float) -> float:
        return value ** 0.5

    def add_resource(self, resource: str, amount: float) -> None:
        setattr(self, resource, getattr(self, resource, 0) + amount)

    def distance(self, b: typing.Union['Field', Coordinates]) -> float:
        if isinstance(b, Field):
            b = b.coordinates
        return self.board.distance(self.coordinates, b)

    def add_coordinates(self, b: Coordinates) -> 'Field':
        return self.board.add_coordinates(self.coordinates, b)

    def get_nearest_field(self, func: typing.Callable[['Field'], bool]) -> typing.Optional['Field']:
        count = 1
        while True:
            tuples = list(sum_to_n(count, 2))
            tuples.append([count, 0])
            coordinates = [Coordinates(*i) for i in tuples]
            extra = []
            for x, y in coordinates:
                extra.append(Coordinates(y, x))
            coordinates.extend(extra)
            extra = []
            for x, y in coordinates:
                extra.append(Coordinates(-x, y))
                extra.append(Coordinates(-x, -y))
                extra.append(Coordinates(x, -y))
            coordinates.extend(extra)
            coordinate_set = set(coordinates)
            for coordinate in coordinate_set:
                target_field = self + coordinate
                if func(target_field):
                    return target_field
            count += 1
            if count > max(self.board.size):
                return None

    def generate_money(self) -> None:
        if self.network:
            money = self.commerce * self.network.production
            logger.debug('Field {} generated {} money for {}.'.format(self.coordinates, money, self.network.name))
            self.network.money += money

    def generate_colors(self) -> None:
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

    def generate_military(self) -> None:
        if self.network:
            military = self.industry * self.network.power
            logger.debug('Field {} generated {} military for {}.'.format(self.coordinates, military, self.network.name))
            self.military += military

    def generate_insight(self) -> None:
        if self.network:
            insight = self.research * self.network.intelligence
            logger.debug('Field {} generated {} insight for {}.'.format(self.coordinates, insight, self.network.name))
            self.network.insight += insight

    def build(self, resource: str, money: float, color1: float, color2: float) -> None:
        if resource in IMMOVABLES and self.network:
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
    def __init__(self, size: typing.Tuple[int, int], game: 'Game') -> None:
        self.game = game
        self.size = size
        self.fields: typing.List[Field] = []
        for i in range(self.size[0]):
            for j in range(self.size[1]):
                self.fields.append(Field(self, Coordinates(i, j)))
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
            data = [[sum([getattr(self.field_dict[Coordinates(i, j)], field_stat)
                          for field_stat in COLORS])
                     for j in range(self.size[1])]
                    for i in range(self.size[0])]
            stddev = (statistics.stdev(itertools.chain(*data)))

    def reset_color(self, color: str) -> None:
        for field in self.fields:
            setattr(field, color, 0)

    def seed_colors(self, peak: float, std: float, color: str) -> None:
        x = random.randint(0, self.size[0] - 1)
        y = random.randint(0, self.size[1] - 1)
        for field in self.fields:
            distance = field - Coordinates(x, y)
            value = normpdf(distance, 0, std) / normpdf(0, 0, std) * peak + getattr(field, color)
            setattr(field, color, value)

    def distance(self, coordinates_a: Coordinates, coordinates_b: Coordinates) -> float:
        vector = self.distance_vector(coordinates_a, coordinates_b)
        return (vector.x ** 2 + vector.y ** 2) ** 0.5

    def distance_vector(self, coordinates_a: Coordinates, coordinates_b: Coordinates) -> Coordinates:
        x_diff = coordinates_b.x - coordinates_a.x
        y_diff = coordinates_b.y - coordinates_a.y
        if x_diff > self.size[0]/2:
            x_diff -= self.size[0]
        elif x_diff < -self.size[0]/2:
            x_diff += self.size[0]
        if y_diff > self.size[1]/2:
            y_diff -= self.size[1]
        elif y_diff < -self.size[1]/2:
            y_diff += self.size[1]
        return Coordinates(x_diff, y_diff)

    def add_coordinates(self, coordinates_a: Coordinates, coordinates_b: Coordinates) -> Field:
        x_add = coordinates_a.x + coordinates_b.x
        y_add = coordinates_a.y + coordinates_b.y
        if x_add < 0:
            x_add += self.size[0]
        elif x_add >= self.size[0]:
            x_add -= self.size[0]
        if y_add < 0:
            y_add += self.size[1]
        elif y_add >= self.size[1]:
            y_add -= self.size[1]
        return self.field_dict.get(Coordinates(x_add, y_add))

    def get_direction(self, start: Coordinates, end: Coordinates) -> Coordinates:
        if start == end:
            result = Coordinates(0,0)
        else:
            vector = self.distance_vector(start, end)
            x = abs(vector.x)
            y = abs(vector.y)
            if x >= y:
                result = Coordinates(1, 0) if vector.x >= 0 else Coordinates(-1, 0)
            else:
                result = Coordinates(0, 1) if vector.y >= 0 else Coordinates(0, -1)
        return result

    def get_field_stat_table(self) -> holoviews.Table:
        data = collections.defaultdict(list)
        for field in self.fields:
            data['x'].append(field.coordinates[0])
            data['y'].append(field.coordinates[1])
            for i in MUTABLE_FIELD_STATS:
                data[i].append(getattr(field, i))
        table = holoviews.Table(data, kdims=['x', 'y'], vdims=MUTABLE_FIELD_STATS)
        return table

    def get_networks_table(self) -> holoviews.Table:
        data = collections.defaultdict(list)
        for field in self.fields:
            data['x'].append(field.coordinates[0])
            data['y'].append(field.coordinates[1])
            data['network'].append(self.game.networks.index(field.network) if field.network else None)
        table = holoviews.Table(data, kdims=['x', 'y'], vdims=['network'])
        return table


class Game:
    def __init__(self, networks: typing.List[Network]) -> None:
        self.networks = networks
        self.network_dict = {network.name: network for network in self.networks}
        self.network_id = {network: i for i, network in enumerate(self.networks)}
        size = int(len(networks) ** 0.5 * FIELDS_PER_EMPIRE ** 0.5)
        self.board = Board((size, size), self)
        self.turn = 0
        self.orders: typing.Dict[Network, typing.List[list]] = {}
        self.trade_requests: typing.List[TradeRequest] = []
        self.trade_request_dict = {trade.id_: trade for trade in self.trade_requests}
        self.alliances = []
        self.trade_counter = 0
        self.place_networks()
        self.data = {stat: [[0] for _ in self.networks] for stat in FIELD_STATS + RESEARCH}

    @staticmethod
    def stats_grid_plot(data):
        plots = []
        for stat in FIELD_STATS:
            subdata = data[data['stat'] == stat]
            overlay = []
            for i in sorted(set(data['network'])):
                overlay.append(
                    holoviews.Curve(subdata[subdata['network'] == i], kdims=['turn'], vdims=('value', stat), label=i))
            plots.append(holoviews.Overlay(overlay))
        return holoviews.Layout(plots)

    @staticmethod
    def field_map_plot(data):
        return holoviews.Layout(
            [holoviews.HeatMap(data.columns(['x', 'y', i]), kdims=['x', 'y'], vdims=i).relabel(i) for i in
             MUTABLE_FIELD_STATS])

    def get_network_map(self, pipe):
        return holoviews.DynamicMap(functools.partial(holoviews.HeatMap, kdims=['x', 'y'], vdims='network'),
                                    streams=[pipe]).redim.range(network=(0, len(self.networks) * 2))

    def get_field_map(self, pipe):
        return holoviews.DynamicMap(self.field_map_plot, streams=[pipe])

    def get_stats_grid(self, pipe):
        return holoviews.DynamicMap(self.stats_grid_plot, streams=[pipe])

    def get_global_stat_table(self, global_stat: str) -> holoviews.Table:
        data = [[i, name, self.data[global_stat][j][i]]
                for j, name in enumerate([i.name for i in self.networks])
                for i in range(self.turn+1)]
        table = holoviews.Table(data, ['turn', 'network'], global_stat)
        return table

    def get_global_stats_table(self) -> holoviews.Table:
        data = [[i, name, global_stat, self.data[global_stat][j][i]]
                for j, name in enumerate([i.name for i in self.networks])
                for i in range(self.turn+1)
                for global_stat in FIELD_STATS + RESEARCH]
        table = holoviews.Table(data, ['turn', 'network', 'stat'], 'value')
        return table

    def get_global_stats_buffer(self) -> pandas.DataFrame:
        data = [[self.turn, name, global_stat, self.data[global_stat][j][self.turn]]
                for j, name in enumerate([i.name for i in self.networks])
                for global_stat in FIELD_STATS + RESEARCH]
        data = pandas.DataFrame(data, columns=['turn', 'network', 'stat', 'value'])
        return data

    def plot_global_stat(self, global_stat):
        data = [[i, name, self.data[global_stat][j][i]] for j, name in enumerate([i.name for i in self.networks])
                for i in range(self.turn+1)]
        table = holoviews.Table(data, ['turn', 'network'], [global_stat])
        plot = table.to(holoviews.Curve).overlay('network')
        return plot

    def gather_data(self) -> None:
        turn_data = {i: [0]*len(self.networks) for i in FIELD_STATS + RESEARCH}
        for field in self.board.fields:
            if field.network:
                network_id = self.network_id[field.network]
                for stat in FIELD_STATS:
                    turn_data[stat][network_id] += getattr(field, stat)
        for research in RESEARCH:
            for network in self.networks:
                network_id = self.network_id[network]
                turn_data[research][network_id] += getattr(network, research)
        for stat, data in turn_data.items():
            for network_id, value in enumerate(data):
                self.data[stat][network_id].append(value)

    def place_networks(self) -> None:
        distances = [0.]
        locations: typing.List[typing.Tuple[Network, Coordinates]] = []
        while min(distances) < MIN_START_DIST:
            distances, locations = [], []
            for network in self.networks:
                x, y = random.randint(0, self.board.size[0] - 1), random.randint(0, self.board.size[1] - 1)
                locations.append((network, Coordinates(x, y)))
            for location in locations:
                for location2 in locations:
                    if location[0] != location2[0]:
                        distances.append(self.board.distance(location[1], location2[1]))

        for network, coordinates in locations:
            self.board.field_dict[coordinates].network = network
            logger.info("Network '{}' starts at {}.".format(network.name, coordinates))

    def do_turn(self) -> None:
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

    def wrap_up_turn(self) -> None:
        for network in self.networks:
            network.log_status()
        self.gather_data()

    def calculate_network_fields(self) -> None:
        for network in self.networks:
            network.fields = []
            for field in self.board.fields:
                if field.network == network:
                    network.fields += [field]
            logging.info("Network '{}' has {} fields.".format(network.name, len(network.fields)))

    def clear_orders(self) -> None:
        logger.info('Clearing orders.')
        self.orders = {}

    def get_orders(self) -> None:
        logger.info('Getting orders.')
        orders = {}
        for network in self.networks:
            try:
                orders[network] = network.issue_orders(self, network.name)
            except:
                logger.info("Network '{}' failed to generate orders for turn {}".format(network.name, self.turn))
                traceback.print_tb(sys.exc_info()[2])
                raise
        self.orders = orders

    def resolve_trade_orders(self) -> None:
        logger.info('Resolving trade orders.')
        for sender, orders in self.orders.items():
            for order in orders:
                try:
                    trade_dict = {RequestTradeOrder: self.resolve_request_trade,
                                  AcceptTradeOrder: self.resolve_accept_trade,
                                  CancelTradeOrder: self.resolve_cancel_trade,
                                  SendOrder: self.resolve_send}
                    trade_dict.get(type(order), lambda x, y: None)(order, sender)
                except:
                    traceback.print_tb(sys.exc_info()[2])
                    raise

    def resolve_request_trade(self, order: RequestTradeOrder, sender: Network) -> None:
        trade_id_ = self.trade_counter
        self.trade_counter += 1
        tradepartner = None
        if order.tradepartner:
            tradepartner = self.network_dict.get(order.tradepartner)
        trade = TradeRequest(trade_id_, sender, order.request_amount, order.request_good,
                             tradepartner, order.offered_amount, order.offered_good)
        self.trade_request_dict[trade_id_] = trade
        logstring = "Network '{}' requested trade of {} {}".format(trade.requester.name,
                                                                   trade.requested_amount,
                                                                   trade.requested_good)
        if trade.tradepartner:
            logstring += " from network '{}".format(trade.tradepartner.name)
        if trade.offered_good and trade.offered_amount:
            logstring += ' for {} {}'.format(trade.offered_amount, trade.offered_good)
        logging.info(logstring + '.()'.format(trade.id_))

    def resolve_accept_trade(self, order: AcceptTradeOrder, sender: Network) -> None:
        trade = self.trade_request_dict.get(order.trade_id)
        if trade:
            logstring = "Network '{}' accepted trade {}".format(sender.name, trade.id_)
            if trade.offered_amount is None and order.offered_amount:
                trade.offered_amount = order.offered_amount
            if trade.offered_tkind is None and order[3]:
                trade.offered_kind = order[3]
                logstring += ' for {} {}'.format(trade.offered_amount, trade.offered_kind)
            if sender == trade.requester:
                trade.confirmed_requester = trade
            if sender == trade.tradepartner:
                trade.confirmed_tradepartner = trade
            logging.info(logstring + '.')

    def resolve_cancel_trade(self, order: CancelTradeOrder, sender: Network) -> None:
        trade = self.trade_request_dict.get(order.trade_id)
        if trade:
            if sender == trade.requester:
                trade.cancelled = True
                logging.info("Network '{}' cancelled trade request {}".format(sender.name, trade.id_))
            elif sender == trade.tradepartner:
                trade.confirmed_tradepartner = False
                logging.info("Network '{}' stepped down from trade {}".format(sender.name, trade.id_))

    def resolve_send(self, order: SendOrder, sender: Network) -> None:
        receiver = self.network_dict.get(order.receiver)
        trade = self.trade_request_dict.get(order.trade_id)
        if order.good in RESOURCES:
            sender_value = getattr(sender, order.good) - order.amount
            if sender_value >= 0 and receiver:
                receiver_value = getattr(receiver, order.good) + order.amount
                setattr(sender, order.good, sender_value)
                setattr(receiver, order.good, receiver_value)
                logging.info(
                    "Network '{}' sent {} {} to network '{}'".format(sender.name, order.amount,
                                                                     order.good, receiver.name))
                if trade:
                    if sender.name == trade.requester:
                        trade.requester_executed = True
                        logging.info("Network '{}' fulfilled trade {} as requester.".format(sender.name, trade.id_))
                    if sender.name == trade.tradepartner:
                        trade.tradepartner_executed = True
                        logging.info("Network '{}' fulfilled trade {} as tradepartner.".format(sender.name, trade.id_))

    def process_move_orders(self) -> None:
        logger.info('Processing move orders.')
        for mover, orders in self.orders.items():
            for order in orders:
                #                try:
                if isinstance(order, MoveOrder):
                    field = self.board.field_dict.get(order.field)
                    target = self.board.field_dict.get(order.target)
                    military = sorted([0, order.military, field.military])[1]
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

    def resolve_combat(self) -> None:
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

                    divid_er = 1 + runner_up[1] / winner[1]

                    field.industry_brut /= divid_er
                    field.research_brut /= divid_er
                    field.commerce_brut /= divid_er

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
                                logger.info('{} money worth of {} was destroyed.'.format(loss * divid_er - loss, i))
                else:
                    field.military = troops[0][1]
                field.moved_military = collections.defaultdict(float)

    def process_build_orders(self) -> None:
        logger.info('Processing build orders.')
        for builder, orders in self.orders.items():
            for order in orders:
                #                try:
                if isinstance(order, BuildOrder):
                    field = self.board.field_dict[order.field]
                    if field.network == builder:
                        field.build(order.resource, order.money, order.color1, order.color2)

    #                except:
    #                    pass

    def generate_stuff(self) -> None:
        logger.info('Generating stuff.')
        for field in self.board.fields:
            field.generate_money()
            field.generate_military()
            field.generate_insight()
        for field in self.board.fields:
            field.generate_colors()

    def process_research_orders(self) -> None:
        logger.info('Processing research orders.')
        for researcher, orders in self.orders.items():
            for order in orders:
                try:
                    if isinstance(order, ResearchOrder):
                        researcher.research(order.subject, order.insight)
                except:
                    traceback.print_tb(sys.exc_info()[2])
                    raise


class TradeRequest:

    def __init__(self, id_: int, requester: Network, requested_amount: float, requested_good: str,
                 tradepartner: Network=None, offered_amount: float=None, offered_good: str=None):
        self.id_ = id_
        self.requester = requester
        self.tradepartner = tradepartner
        self.requested_amount = requested_amount
        self.requested_good = requested_good if requested_good in RESOURCES else None
        self.offered_amount = offered_amount
        self.offered_good = offered_good if offered_good in RESOURCES else None
        self.confirmed_tradepartner = False
        self.confirmed_requester = False
        self.requester_executed = False
        self.tradepartner_executed = False
        self.cancelled = False


def sum_to_n(n: int, size: int, limit=None) -> typing.List[list]:
    """Produce all lists of `size` positive integers in decreasing order
    that add up to `n`."""
    if size == 1:
        yield [n]
        return
    if limit is None:
        limit = n
    start = (n + size - 1) // size
    stop = min(limit, n - size + 1) + 1
    for i in range(start, stop):
        for tail in sum_to_n(n - i, size - 1, i):
            yield [i] + tail


def normpdf(x: float, mu: float, sigma: float) -> float:
    u = (x - mu) / sigma
    y = (1 / (math.sqrt(2 * math.pi) * sigma ** 2)) * math.exp(-u * u / 2)
    return y
