import matplotlib.pyplot as plt
import asyncio
import random
import string
import calendar
import time
import logging
import numpy as np
import copy


logging.basicConfig(level=logging.ERROR, format="%(levelname)s:%(name)s: %(message)s")


class Message:
    _next_id = 0

    def __init__(self, content, is_confirmation=False, id=None):
        self.content = content
        self.timestamp = self._generate_timestamp()
        self.id = self._generate_id() if id is None else id
        if is_confirmation:
            self.expiration_timestamp = self._calculate_expiration_timestamp()

    def _calculate_expiration_timestamp(self):
        return self.timestamp + EXPIRATION_TIME

    def _generate_id(self):
        new_id = Message._next_id
        Message._next_id += 1
        if Message._next_id > MAX_MESSAGE_ID:
            Message._next_id = 0

        return new_id

    def _generate_timestamp(self):
        gmt = time.gmtime()
        timestamp = calendar.timegm(gmt)
        return timestamp

    def get_content(self):
        return self.content

    def get_timestamp(self):
        return self.timestamp

    def get_id(self):
        return self.id

    def expired(self):
        if (
            self.get_expiration_timestamp()
            and self.get_expiration_timestamp() <= time.time()
        ):
            return True
        return False

    def set_id(self, new_id):
        self.id = new_id

    def get_is_confirmation_message(self):
        return hasattr(self, "expiration_timestamp")

    def get_expiration_timestamp(self):
        return getattr(self, "expiration_timestamp", None)


class Internet:
    addresses = {}
    logger = logging.getLogger("Internet")  # Create logger for the class

    @staticmethod
    async def send_message(sender_ip, receiver_ip, msg: Message):
        message = copy.copy(msg)
        Internet.logger.debug(f"Sending message from {sender_ip} to {receiver_ip}")
        await Internet._add_delay()

        Internet._add_error(message)

        if Internet._message_fail():
            Internet.logger.warning("Message failed to reach destination")
            return

        receiver = Internet.addresses.get(receiver_ip)
        if receiver:
            await receiver.receive_message(sender_ip, message)
        else:
            logger.error(f"Can't recognize computer with ip {receiver_ip}")

    @staticmethod
    def add_computer(computer: "Computer"):
        Internet.addresses[computer.get_ip()] = computer

    @staticmethod
    async def _add_delay():
        delay = np.random.normal(MEDIUM_DELAY_TIME, DELAY_TIME_STANDARD_DEVIATION)
        if delay < 0:
            delay = delay * -1
        await asyncio.sleep(delay)
        Internet.logger.debug(f"Delay of {delay} seconds added.")

    @staticmethod
    def _add_error(message):
        if random.random() < ERROR_CHANCE:
            new_id = message.get_id() + int(
                random.randrange(-MAX_MESSAGE_ID // 10, MAX_MESSAGE_ID // 10)
            )
            message.set_id(new_id)
            Internet.logger.debug(f"Message ID to {new_id} modified due to error.")

    @staticmethod
    def _message_fail():
        if random.random() < FAIL_CHANCE:
            return True
        return False


class Computer:
    def __init__(self, internet: Internet, ip: string):
        self.ip = ""
        self._connected_to = []

    def get_ip(self):
        return self.ip

    async def run(self):
        pass

    def receive_message(self, ip, message):
        pass

    async def send_message(self, recipient_ip, message):
        await self.internet.send_message(self.ip, recipient_ip, message)

    def connect(self, computer):
        if computer.get_ip() not in self._connected_to:
            self._connected_to.append(computer.get_ip())
            computer.connect(self)
        return


class Sender(Computer):
    def __init__(self, internet, ip):
        self.internet = internet
        self.ip = ip
        self._connected_to = []
        self._is_message_confirmed = {}
        self.logger = logging.getLogger(self.ip)  # Create logger for the class

    async def run(self):
        self.logger.info("Computer A is running")
        for recipient_ip in self._connected_to:
            asyncio.create_task(self.send_message_routine(recipient_ip))

        while True:
            await asyncio.sleep(1)  # Sleep for a short duration to prevent busy waiting

    async def send_message_routine(self, recipient_ip):
        while True:
            # self.logger.info(f"Creating new message to {recipient_ip}")
            new_message = self._create_message()
            self.add_new_unconfirmed_message(recipient_ip, new_message.get_id())
            asyncio.create_task(self.send_message(recipient_ip, new_message))
            asyncio.create_task(self.confirmation_routine(recipient_ip, new_message))
            await asyncio.sleep(SEND_NEW_MESSAGE_TIME)

    def add_new_unconfirmed_message(self, recipient_ip, message_id):
        try:
            if recipient_ip not in self._is_message_confirmed:
                self._is_message_confirmed[recipient_ip] = {}
            self._is_message_confirmed[recipient_ip][message_id] = False
            self.logger.warning(
                f"waiting for confirmation from message {message_id} from {recipient_ip}"
            )
        except Exception as e:
            self.logger.warning(
                f"Error occurred while adding new unconfirmed message: {e}"
            )

    def confirm_message(self, recipient_ip, message_id):
        try:
            if self._is_message_confirmed[recipient_ip][message_id] == False:
                self._is_message_confirmed[recipient_ip][message_id] = True
            else:
                self.logger.warning("Message is already confirmed")
        except KeyError as e:
            self.logger.warning(
                f"Error confirming message: {e}. Message or recipient not found."
            )
        except Exception as e:
            self.logger.warning(f"An error occurred while confirming message: {e}")

    async def receive_message(self, sender_ip, message):
        self.logger.info(
            f"Received message (content: {message.get_content()}, id: {message.get_id()}, timestamp: {message.get_timestamp()}) from {sender_ip}"
        )
        if (
            message.get_id() >= 0
            and message.get_is_confirmation_message()
            and not message.expired()
        ):
            self.confirm_message(sender_ip, message.get_id())

    async def confirmation_routine(self, recipient_ip, message):
        global fails, successes
        retry_number = 0
        while (
            not self._check_confirmation(recipient_ip, message.get_id())
        ) and retry_number < MAX_RETRIES:
            self.logger.debug(
                f"retry n{retry_number+1} to send message {message.get_id()} to {recipient_ip}"
            )
            await self.send_message(recipient_ip, message)
            retry_number += 1

        if retry_number == MAX_RETRIES:
            self.logger.error(
                f"Failed to send message (content: {message.get_content()}, id: {message.get_id()}, timestamp: {message.get_timestamp()}) to IP: {recipient_ip}"
            )
            fails += 1
        else:
            self.logger.info(
                f"Confirmed receivement of message (txt:{message.get_content()},id:{message.get_id()}) sent to {recipient_ip}"
            )
            successes += 1

    def _check_confirmation(self, recipient_ip, message_id):
        try:
            try_until = time.time() + RETRY_TIME
            while time.time() < try_until:
                if self._is_message_confirmed[recipient_ip][message_id]:
                    self._is_message_confirmed[recipient_ip].pop(message_id)
                    return True
            return False
        except KeyError as e:
            # self.logger.warning(f"Error checking confirmation: {e}. Message or recipient not found.")
            self.logger.warning(f"Cannot find id {e}")
            return False
        except Exception as e:
            self.logger.warning(f"An error occurred while checking confirmation: {e}")
            return False

    def _create_message(self):
        global unique_messages_sent
        message_text = "".join(
            random.choice(string.ascii_uppercase + string.digits)
            for _ in range(MESSAGE_SIZE)
        )
        message = Message(message_text)

        unique_messages_sent += 1

        return message


class Receiver(Computer):
    def __init__(self, internet: Internet, ip):
        self.internet = internet
        self.ip = ip
        self._connected_to = []
        self.logger = logging.getLogger(self.ip)  # Create logger for the class

    async def receive_message(self, sender_ip, message):
        self.logger.info(
            f"Received message (content: {message.get_content()}, id: {message.get_id()}, timestamp: {message.get_timestamp()}) from IP: {sender_ip}"
        )
        if message.get_id() >= 0:
            await self.send_confirmation_message(sender_ip, message.get_id())
        else:
            self.logger.debug(f"Got message with invalid id: {message.get_id()}")

    async def send_confirmation_message(self, recipient_ip, message_id):
        message = self._create_confirmation_message(message_id)
        await self.send_message(recipient_ip, message)

    def _create_confirmation_message(self, id):
        message_text = "receivement confirmed"
        message = Message(message_text, is_confirmation=True, id=id)
        return message


async def main():
    global successes, fails

    internet = Internet()
    computer_a = Sender(internet, "a")
    computer_d = Sender(internet, "d")
    computer_b = Receiver(internet, "b")
    computer_c = Receiver(internet, "c")

    computer_a.connect(computer_b)
    computer_a.connect(computer_c)
    computer_d.connect(computer_b)
    computer_d.connect(computer_c)

    internet.add_computer(computer_a)
    internet.add_computer(computer_b)
    internet.add_computer(computer_c)
    internet.add_computer(computer_d)

    # Start the run coroutine by creating a task
    task = asyncio.create_task(computer_a.run())
    task = asyncio.create_task(computer_d.run())

    # Sleep for one minute
    await asyncio.sleep(EXPERIMENT_TIME)

    # Calculate the proportion of successes and failures
    total_messages = successes + fails
    success_proportion = successes / total_messages
    fail_proportion = fails / total_messages

    # Plot the results
    labels = ["Successes", "Failures"]
    sizes = [success_proportion, fail_proportion]
    plt.pie(sizes, labels=labels, autopct="%1.1f%%")
    plt.title("Proportion of Successes and Failures")
    plt.show()

    print(success_proportion)
    # print(unique_messages_sent)
    # print(total_messages)

    # Cancel the task to stop the event loop
    task.cancel()


if __name__ == "__main__":
    errors = [0.1, 0.2, 0.3, 0.4, 0.5]
    for error in errors:
        EXPERIMENT_TIME = 60 * 2

        ERROR_CHANCE = error
        FAIL_CHANCE = error / 4

        RETRY_TIME = 0.25
        MAX_RETRIES = 5

        MEDIUM_DELAY_TIME = 0
        DELAY_TIME_STANDARD_DEVIATION = 0.5

        SEND_NEW_MESSAGE_TIME = 0.5

        EXPIRATION_TIME = 3

        MAX_MESSAGE_ID = 100
        MESSAGE_SIZE = 2

        successes = 0
        fails = 0
        unique_messages_sent = 0

        asyncio.run(main())
