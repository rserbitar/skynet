#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest

import skynet.main


"""
Description
"""

__author__ = 'serbitar'

class TestBoard:

    def test_distance_vector(self):
        board = skynet.main.Board((20, 20), None)
        a = skynet.main.Coordinates(0, 0)
        b = skynet.main.Coordinates(5, 5)
        vector = board.distance_vector(a, b)
        assert vector == (5, 5)

    def test_distance_vector2(self):
        board = skynet.main.Board((20, 20), None)
        a = skynet.main.Coordinates(0, 0)
        b = skynet.main.Coordinates(15, 15)
        vector = board.distance_vector(a, b)
        assert vector == (-5, -5)

    def test_distance_vector3(self):
        board = skynet.main.Board((20, 20), None)
        a = skynet.main.Coordinates(5, 19)
        b = skynet.main.Coordinates(6, 1)
        vector = board.distance_vector(a, b)
        assert vector == (1, 2)

    def test_get_direction(self):
        board = skynet.main.Board((20, 20), None)
        a = skynet.main.Coordinates(0, 0)
        b = skynet.main.Coordinates(0, 5)
        direction = board.get_direction(a,b)
        assert direction == (0,1)

    def test_get_direction2(self):
        board = skynet.main.Board((20, 20), None)
        a = skynet.main.Coordinates(0, 6)
        b = skynet.main.Coordinates(0, 1)
        direction = board.get_direction(a,b)
        assert direction == (0, -1)
