import random

deck = list(range(52))
random.shuffle(deck)

list1, list2 = deck = deck[:26], deck[26:]



