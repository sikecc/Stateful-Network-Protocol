"""
war card game client and server
"""
import asyncio
from collections import namedtuple
from enum import Enum
import logging
import random
import socket
import socketserver
import threading
import sys
import selectors
import pickle
import functools


players = []

"""
Namedtuples work like classes, but are much more lightweight so they end
up being faster. It would be a good idea to keep objects in each of these
for each game which contain the game's state, for instance things like the
socket, the cards given, the cards still available, etc.
"""
Game = namedtuple("Game", ["p1", "p2"])


class Command(Enum):
    """
    The byte values sent as the first byte of any message in the war protocol.
    """
    WANTGAME = 0
    GAMESTART = 1
    PLAYCARD = 2
    PLAYRESULT = 3


class Result(Enum):
    """
    The byte values sent as the payload byte of a PLAYRESULT message.
    """
    WIN = 0
    DRAW = 1
    LOSE = 2


def readexactly(sock, numbytes):
    """
    Accumulate exactly `numbytes` from `sock` and return those. If EOF is found
    before numbytes have been received, be sure to account for that here or in
    the caller.
    """

    data = b''
    while len(data) != numbytes:
        current = sock.recv(1)
        data += current
        if len(current) == 0 and len(data) != numbytes:
            print('THERE IS AN ERROR.')
            sock.close()
            return

    return data


def kill_game(client1, client2):
    """
    TODO: If either client sends a bad message, immediately nuke the game.
    """
    client1.close()
    client2.close()

    pass


def compare_cards(card1, card2):
    """
    TODO: Given an integer card representation, return -1 for card1 < card2,
    0 for card1 = card2, and 1 for card1 > card2
    """
    # logging.debug(card1)
    # logging.debug(card2)
    if (card1 % 13) < (card2 % 13):
        return 2
    elif (card1 % 13) > (card2 % 13):
        return 0
    else:
        return 1


def deal_cards():
    """
    TODO: Randomize a deck of cards (list of ints 0..51), and return two
    26 card "hands."
    """
    cards = list(range(52))
    random.shuffle(cards)
    
    both_half = [(cards[:26]), (cards[26:])]
    return both_half


def check_card(card, deck):
    if card not in deck:
        return False
    return True


async def handle_game(player1, player2):
    """
    This is the main component of the game.
    f_client and s_client are 2 client sockets that connected as a pair
    They play the game here and the error checking is done here
    """

    split_deck = deal_cards()
    c1_cards = split_deck[0]
    c2_cards = split_deck[1]

    c1_used = [False] * 26
    c2_used = [False] * 26

    try:

        print("Players in game: ", player1, player2)
        
        f_client_data = await player1[0].readexactly(2)
        s_client_data = await player2[0].readexactly(2)

        

        if(f_client_data[1] != 0) or s_client_data[1] != 0:
            print('ERROR... User does not enter in 0 for the first time')
            kill_game(player1[1], player2[1])
            return

        # Clients are ready for their cards
        player1[1].write(bytes(([Command.GAMESTART.value]+c1_cards)))
        player2[1].write(bytes(([Command.GAMESTART.value]+c2_cards)))

        total_turns = 0

        while total_turns < 26:

            f_client_data = await player1[0].readexactly(2)
            s_client_data = await player2[0].readexactly(2)

            # Check if first byte was 'play card'
            if f_client_data[0] != 2 and s_client_data[0] != 2:
                print('Error... User does not enter in 2.')
                kill_game(player1[1], player2[1])
                return

            # Check if card is in deck

            if check_card(f_client_data[1], split_deck[0]) is False\
                    or check_card(s_client_data[1], split_deck[1]) is False:
                print('Error... A clients card does not match card dealt')
                kill_game(player1[1], player2[1])
                return

            # Check if card was already used
            for x in range(0, 26):

                if f_client_data[1] == c1_cards[x] or \
                        s_client_data[1] == c2_cards[x]:

                    if f_client_data[1] == c1_cards[x]:

                        if c1_used[x] is False:
                            c1_used[x] = True
                        else:
                            print('Error: A client tried to use '
                                  'the same card again ')
                            kill_game(player1[1], player2[1])
                            return

                    if s_client_data[1] == c2_cards[x]:
                        if c2_used[x] is False:
                            c2_used[x] = True
                        else:
                            print('Error: A client tried to use '
                                  'the same card again ')
                            kill_game(player1[1], player2[1])
                            return

            # Get the results for the first and second client
            c1_result = compare_cards(f_client_data[1], s_client_data[1])
            c2_result = compare_cards(s_client_data[1], f_client_data[1])

            # Concat the command to send with the result
            c1_send_result = [Command.PLAYRESULT.value, c1_result]
            c2_send_result = [Command.PLAYRESULT.value, c2_result]

            # Write back to the client
            player1[1].write(bytes(c1_send_result))
            player2[1].write(bytes(c2_send_result))

            total_turns += 1

        # Close the connections
        kill_game(player1[1], player2[1])

    except ConnectionResetError:
        logging.error("ConnectionResetError")
        return 0
    except asyncio.streams.IncompleteReadError:
        logging.error("asyncio.streams.IncompleteReadError")
        return 0
    except OSError:
        logging.error("OSError")
        return 0



async def pair_connection(reader, writer, pairing_clients):
    """
    Handler for connections to server
    """
    logging.debug("Waiting...")
    pairing_clients.append((reader, writer))
    logging.debug("Players connected %d ", len(pairing_clients))

    if len(pairing_clients) == 2:
        logging.debug("Start game")
        await handle_game(pairing_clients[0], pairing_clients[1])

        pairing_clients.clear()
        return

def serve_game(host, port):
    """
    Runs an asyncio event loop for every client that it connects.
    Will run forever until server presses control+c.
    """

    loop = asyncio.get_event_loop()

    my_handler = functools.partial(pair_connection, pairing_clients=players)
    conn = asyncio.start_server(my_handler, host, port, loop=loop)
    server = loop.run_until_complete(conn)

    # Serve requests until Ctrl+C is pressed
    print('Serving on {}'.format(server.sockets[0].getsockname()))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass

    # Close the server
    server.close()
    loop.run_until_complete(server.wait_closed())

    loop.close()


async def limit_client(host, port, loop, sem):
    """
    Limit the number of clients currently executing.
    You do not need to change this function.
    """
    async with sem:
        return await client(host, port, loop)


async def client(host, port, loop):
    """
    Run an individual client on a given event loop.
    You do not need to change this function.
    """
    try:

        reader, writer = await asyncio.open_connection(host, port, loop=loop)
        # send want game
        myscore = 0

        writer.write(b"\0\0")
        card_msg = await reader.readexactly(27)

        for card in card_msg[1:]:

            writer.write(bytes([Command.PLAYCARD.value, card]))
            result = await reader.readexactly(2)

            if result[1] == Result.WIN.value:
                myscore += 1
            elif result[1] == Result.LOSE.value:
                myscore -= 1
        if myscore > 0:
            result = "won"
        elif myscore < 0:
            result = "lost"
        else:
            result = "drew"

        print("Result: ", result)
        logging.debug("Game complete, I %s", result)
        writer.close()
        return 1
    except ConnectionResetError:
        logging.error("ConnectionResetError")
        return 0
    except asyncio.streams.IncompleteReadError:
        logging.error("asyncio.streams.IncompleteReadError")
        return 0
    except OSError:
        logging.error("OSError")
        return 0


def main(args):
    """
    launch a client/server
    """
    host = args[1]
    port = int(args[2])
    if args[0] == "server":
        try:
            serve_game(host, port)
        except KeyboardInterrupt:
            pass
        return
    else:
        loop = asyncio.get_event_loop()

    if args[0] == "client":
        loop.run_until_complete(client(host, port, loop))
    elif args[0] == "clients":
        sem = asyncio.Semaphore(1000)
        num_clients = int(args[3])
        clients = [limit_client(host, port, loop, sem)
                   for x in range(num_clients)]
        async def run_all_clients():
            """
            use `as_completed` to spawn all clients simultaneously
            and collect their results in arbitrary order.
            """
            completed_clients = 0
            for client_result in asyncio.as_completed(clients):
                completed_clients += await client_result
            return completed_clients
        res = loop.run_until_complete(
            asyncio.Task(run_all_clients(), loop=loop))
        logging.info("%d completed clients", res)

    loop.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main(sys.argv[1:])
