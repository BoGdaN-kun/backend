import asyncio
import json
import os
from datetime import datetime, timezone
import yfinance as yf
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

# Kafka configuration
BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

# Topic for real-time stock ticks (all symbols will go here)
TICKS_TOPIC = "realtime_ticks"
# Topic for receiving subscription requests from other services (e.g., consumer/frontend)
SUBSCRIPTION_REQUEST_TOPIC = "ticker_subscription_requests"

# Global set to keep track of actively subscribed symbols
# Initialize with a default symbol, e.g., AAPL
active_symbols = {"AAPL"}

# WebSocket instance (will be initialized in main)
websocket_instance = None

# Declare producer and subscription_consumer here, but initialize them in main()
producer = None
subscription_consumer = None

async def async_message_handler(msg: dict) -> None:
    """
    Handles incoming messages from the Yahoo Finance WebSocket.
    Parses the message and sends it to the TICKS_TOPIC.
    """
    global producer # Access the global producer instance

    try:
        # Yahoo Finance WebSocket messages have 'id' for symbol and 'time' for timestamp
        symbol = msg.get("id")
        ts_ms = int(msg.get("time"))
        price = msg.get("price")

        if not all([symbol, ts_ms, price]):
            print(f"Skipping incomplete message: {msg}")
            return

        # Convert timestamp from milliseconds to ISO format with UTC timezone
        #ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat(timespec="seconds") + "Z"
        ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        tick = {
            "symbol": symbol,
            "ts": ts,
            "price": price,
        }
        # Send the tick to the generic TICKS_TOPIC
        if producer: # Ensure producer is initialized before sending
            await producer.send(TICKS_TOPIC, tick)
            print(f"Sent to Kafka ({TICKS_TOPIC}): {tick}") # Optional: for debugging
        else:
            print("Producer not initialized, cannot send message.")
    except (ValueError, TypeError) as e:
        print(f"Could not parse message: {msg}. Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred in message handler: {e}")

async def _subscribe_listener():
    """
    Listens for subscription requests on the SUBSCRIPTION_REQUEST_TOPIC.
    Dynamically updates the active_symbols set and the WebSocket subscription.
    """
    global subscription_consumer # Access the global consumer instance

    if not subscription_consumer:
        print("Subscription consumer not initialized.")
        return

    await subscription_consumer.start()
    print(f"Listening for subscription requests on {SUBSCRIPTION_REQUEST_TOPIC}...")
    try:
        async for msg in subscription_consumer:
            request = msg.value
            symbol_to_manage = request.get("symbol")
            action = request.get("action") # 'subscribe' or 'unsubscribe'

            if not all([symbol_to_manage, action]):
                print(f"Invalid subscription request: {request}")
                continue

            symbol_to_manage = symbol_to_manage.upper() # Ensure uppercase for consistency

            if action == "subscribe":
                if symbol_to_manage not in active_symbols:
                    active_symbols.add(symbol_to_manage)
                    print(f"Added {symbol_to_manage} to active symbols. Current: {list(active_symbols)}")
                    if websocket_instance:
                        # Resubscribe to all active symbols to ensure new ones are included
                        await websocket_instance.subscribe(list(active_symbols))
                        print(f"WebSocket resubscribed to: {list(active_symbols)}")
                else:
                    print(f"{symbol_to_manage} already in active symbols.")
            elif action == "unsubscribe":
                if symbol_to_manage in active_symbols:
                    active_symbols.remove(symbol_to_manage)
                    print(f"Removed {symbol_to_manage} from active symbols. Current: {list(active_symbols)}")
                    if websocket_instance:
                        # Resubscribe to remaining active symbols
                        await websocket_instance.subscribe(list(active_symbols))
                        print(f"WebSocket resubscribed to: {list(active_symbols)}")
                else:
                    print(f"{symbol_to_manage} not in active symbols.")
            else:
                print(f"Unknown action '{action}' for symbol {symbol_to_manage}")

    except asyncio.CancelledError:
        print("Subscription listener task cancelled.")
    except Exception as e:
        print(f"Error in subscription listener: {e}")
    finally:
        if subscription_consumer:
            await subscription_consumer.stop()

async def main() -> None:
    """
    Main function to start Kafka producer, subscription listener, and Yahoo Finance WebSocket.
    """
    global websocket_instance, producer, subscription_consumer # Declare as global to modify the instances

    # Initialize Kafka producer and consumer within the async context
    producer = AIOKafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    subscription_consumer = AIOKafkaConsumer(
        SUBSCRIPTION_REQUEST_TOPIC,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        group_id="producer-subscription-group",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

    # Start Kafka producer
    await producer.start()
    print("Kafka Producer started.")

    # Start Kafka subscription request listener in a background task
    subscription_task = asyncio.create_task(_subscribe_listener())

    try:
        print("Connecting to Yahoo Finance WebSocket…")
        async with yf.AsyncWebSocket() as ws:
            websocket_instance = ws # Store the WebSocket instance globally
            # Initial subscription
            await ws.subscribe(list(active_symbols))
            print(f"Initially subscribed to {', '.join(active_symbols)}; streaming ticks to Kafka.")
            # Listen for incoming real-time messages
            await ws.listen(async_message_handler)
    except asyncio.CancelledError:
        print("Main WebSocket task cancelled.")
    except Exception as e:
        print(f"An error occurred in main: {e}")
    finally:
        print("Flushing final messages and closing producer...")
        if producer:
            await producer.stop()
        subscription_task.cancel() # Cancel the subscription listener task
        await subscription_task # Await its completion
        print("Producer and subscription listener stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Application stopped by user.")
    except Exception as e:
        print(f"Application encountered an error: {e}")

