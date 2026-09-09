#!/usr/bin/env python3

import asyncio
import json
import math
import threading

import websockets
import rclpy

from rclpy.node import Node
from rclpy.action import ActionServer, GoalResponse, CancelResponse

from interaction_skills.msg import SetExpression
from std_msgs.msg import String
from std_srvs.srv import SetBool
from interaction_skills.action import LookAt
# ---------------------------------------------------------------------------
# Global asyncio state
# ---------------------------------------------------------------------------

asyncio_loop = None
message_queue = None

# The currently connected browser WebSocket.
browser_ws = None

# Lock protecting browser_ws from the ROS thread.
browser_ws_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Expression mapping
# ---------------------------------------------------------------------------

EXPRESSION_MAP = {
    "neutral": "neutral",
    "angry": "anger",
    "sad": "sad",
    "happy": "happy",
    "surprised": "surprise",
    "tired": "sleepy",
    "bored": "sleepy",
    "asleep": "sleepy",
    "concerned": "concerned",
}


# ---------------------------------------------------------------------------
# ROS2 node
# ---------------------------------------------------------------------------

class VizijFaceBridge(Node):

    def __init__(self):
        super().__init__("vizij_face_bridge")

        # ---------------------------------------------------------------
        # Expression
        # ---------------------------------------------------------------

        self.set_expression_subscription = self.create_subscription(
            SetExpression,
            "/skill/set_expression",
            self.set_expression_cb,
            10,
        )
        self.set_visemes_service = self.create_service(
            SetBool,
            "/vizij/set_visemes_enabled",
            self.set_visemes_enabled_cb,
        )
        # ---------------------------------------------------------------
        # Gaze
        # ---------------------------------------------------------------

        self.gaze_action_server = ActionServer(
            self,
            LookAt,
            "/robot_face/look_at",
            self.gaze_execute_cb,
            goal_callback=self.gaze_goal_cb,
            cancel_callback=self.gaze_cancel_cb,
        )

        # ---------------------------------------------------------------
        # Speech metadata
        #
        # The Coqui TTS node publishes:
        #
        #   /tts/speech [std_msgs/msg/String]
        #
        # with JSON:
        #
        #   {
        #       "text": "Hola",
        #       "duration": 1.42
        #   }
        #
        # We forward this to the Vizij browser.
        # ---------------------------------------------------------------

        self.speech_subscription = self.create_subscription(
            String,
            "/tts/speech",
            self.speech_cb,
            10,
        )

        # ---------------------------------------------------------------
        # Startup logging
        # ---------------------------------------------------------------

        self.get_logger().info(
            "Vizij Face Bridge running"
        )

        self.get_logger().info(
            "  Expression topic: /skill/set_expression "
            "[interaction_skills/msg/SetExpression]"
        )

        self.get_logger().info(
            "  Gaze topic:       /robot_face/look_at "
            "[geometry_msgs/msg/Vector3]"
        )

        self.get_logger().info(
            "  Speech topic:     /tts/speech "
            "[std_msgs/msg/String]"
        )

        self.get_logger().info(
            "  WebSocket:        ws://0.0.0.0:9001"
        )

    def set_visemes_enabled_cb(
        self,
        request: SetBool.Request,
        response: SetBool.Response,
    ):
        enabled = bool(request.data)

        payload = {
            "type": "visemes_enabled",
            "enabled": enabled,
        }

        sent = self.send_to_browser(payload)

        if sent:
            response.success = True
            response.message = (
                f"Visemes {'enabled' if enabled else 'disabled'}"
            )

            self.get_logger().info(
                f"Visemes -> WS: enabled={enabled}"
            )
        else:
            response.success = False
            response.message = (
                "Failed to send viseme state to browser"
            )

        return response

    # -------------------------------------------------------------------
    # Expression callback
    # -------------------------------------------------------------------

    def set_expression_cb(self, msg: SetExpression):
        try:
            expr = msg.expression.expression.lower().strip()
        except Exception as exc:
            self.get_logger().error(
                f"Failed to read expression: {exc}"
            )
            return

        if expr not in EXPRESSION_MAP:
            self.get_logger().warning(
                f"Expression '{expr}' not mapped"
            )
            return

        semantic = EXPRESSION_MAP[expr]

        # ---------------------------------------------------------------
        # SetExpression contains the arousal value.
        # In this system, arousal is expected to be in the range [0.0, 1.0].
        # ---------------------------------------------------------------

        arousal = float(msg.arousal)

        # Keep the value in the valid range.
        arousal = max(
            0.0,
            min(1.0, arousal),
        )

        payload = {
            "type": "pose",
            "semanticKey": semantic,
            "value": arousal,
        }

        sent = self.send_to_browser(payload)

        if sent:
            self.get_logger().info(
                f"SetExpression -> WS: "
                f"{expr} -> {semantic} = {arousal:.3f}"
            )

    # -------------------------------------------------------------------
    # Gaze action
    # -------------------------------------------------------------------

    def gaze_goal_cb(self, goal_request):
        self.get_logger().info(
            f"Received gaze goal: "
            f"policy='{goal_request.policy}'"
        )

        return GoalResponse.ACCEPT


    def gaze_cancel_cb(self, goal_handle):
        self.get_logger().info(
            "Gaze goal cancellation requested"
        )

        return CancelResponse.ACCEPT


    def gaze_execute_cb(self, goal_handle):

        request = goal_handle.request

        policy = request.policy

        target = request.target

        # ---------------------------------------------------------------
        # Build WebSocket message
        # ---------------------------------------------------------------

        payload = {
            "type": "gaze",
            "policy": policy,
        }

        # ---------------------------------------------------------------
        # Include target if provided
        # ---------------------------------------------------------------

        if target.header.frame_id:
            payload["target"] = {
                "frame_id": target.header.frame_id,
                "x": float(target.point.x),
                "y": float(target.point.y),
                "z": float(target.point.z),
            }

        # ---------------------------------------------------------------
        # Forward to Vizij browser
        # ---------------------------------------------------------------

        sent = self.send_to_browser(payload)

        if sent:

            self.get_logger().info(
                f"Gaze -> WS: "
                f"policy='{policy}' "
                f"target={payload.get('target')}"
            )

            goal_handle.succeed()

        else:

            self.get_logger().error(
                "Failed to send gaze command to browser"
            )

            goal_handle.abort()

        return LookAt.Result()

    # -------------------------------------------------------------------
    # Speech callback
    # -------------------------------------------------------------------

    def speech_cb(self, msg: String):
        """
        Receive speech metadata from the Coqui TTS node.

        Expected ROS message:

            /tts/speech [std_msgs/msg/String]

        Message contents:

            {
                "text": "Hola, ¿cómo estás?",
                "duration": 1.42
            }

        The bridge does NOT generate or play audio.

        It simply forwards the metadata to the Vizij browser:

            {
                "type": "say",
                "text": "Hola, ¿cómo estás?",
                "duration": 1.42
            }

        The browser can then build a phoneme/viseme timeline
        using the actual generated audio duration.
        """

        raw = msg.data.strip()

        if not raw:
            self.get_logger().warning(
                "Received empty /tts/speech message"
            )
            return

        # ---------------------------------------------------------------
        # Parse JSON
        # ---------------------------------------------------------------

        try:
            data = json.loads(raw)

        except json.JSONDecodeError as exc:
            self.get_logger().error(
                f"Invalid JSON received on /tts/speech: {exc}"
            )

            self.get_logger().error(
                f"Raw message: {raw}"
            )

            return

        if not isinstance(data, dict):
            self.get_logger().error(
                "/tts/speech JSON is not an object"
            )
            return

        # ---------------------------------------------------------------
        # Extract text
        # ---------------------------------------------------------------

        text = data.get("text", "")

        if not isinstance(text, str):
            self.get_logger().error(
                "/tts/speech 'text' is not a string"
            )
            return

        text = text.strip()

        if not text:
            self.get_logger().warning(
                "/tts/speech contains empty text"
            )
            return

        # ---------------------------------------------------------------
        # Extract duration
        # ---------------------------------------------------------------

        try:
            duration = float(
                data.get("duration", 0.0)
            )

        except (TypeError, ValueError):
            self.get_logger().error(
                "Invalid duration in /tts/speech"
            )
            return

        if not math.isfinite(duration):
            self.get_logger().error(
                "Non-finite duration in /tts/speech"
            )
            return

        if duration <= 0.0:
            self.get_logger().warning(
                f"Invalid speech duration: {duration}"
            )
            return

        # ---------------------------------------------------------------
        # Forward to browser
        # ---------------------------------------------------------------

        payload = {
            "type": "say",
            "text": text,
            "duration": duration,
        }

        sent = self.send_to_browser(payload)

        if sent:
            self.get_logger().info(
                f"Speech -> WS: "
                f"'{text}' "
                f"duration={duration:.3f}s"
            )

    # -------------------------------------------------------------------
    # ROS -> WebSocket helper
    # -------------------------------------------------------------------

    def send_to_browser(self, payload):
        """
        Safely put a message into the asyncio WebSocket queue
        from the ROS2 thread.
        """

        global asyncio_loop
        global message_queue

        if asyncio_loop is None:
            self.get_logger().warning(
                "Asyncio loop is not ready; "
                "dropping WS message"
            )
            return False

        if message_queue is None:
            self.get_logger().warning(
                "WebSocket message queue is not ready; "
                "dropping WS message"
            )
            return False

        asyncio_loop.call_soon_threadsafe(
            message_queue.put_nowait,
            payload,
        )

        return True


# ---------------------------------------------------------------------------
# Browser -> ROS helper
# ---------------------------------------------------------------------------

def handle_browser_message(payload):
    """
    Handle messages received from the React/Vizij browser.

    The old 'tts_finished' message is no longer required because
    the /skill/say action is now owned by the Coqui TTS node.

    The bridge currently only needs to log browser -> ROS messages.
    """

    if not isinstance(payload, dict):
        print(
            "Ignoring non-object browser message:",
            payload,
        )
        return

    message_type = payload.get("type")

    # -----------------------------------------------------------------------
    # Legacy TTS finished message
    # -----------------------------------------------------------------------
    #
    # We deliberately do nothing with this anymore.
    #
    # /skill/say is now handled completely by tts_ros:
    #
    #   generate -> play -> finish action
    #
    # The browser is no longer responsible for completing the ROS action.
    # -----------------------------------------------------------------------

    if message_type == "tts_finished":
        print(
            "Ignoring legacy browser tts_finished message"
        )
        return

    # -----------------------------------------------------------------------
    # Other browser messages
    # -----------------------------------------------------------------------

    print(
        "Browser -> ROS:",
        payload,
    )


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------

async def ws_handler(ws):

    global browser_ws

    print(
        "Browser connected:",
        getattr(
            ws,
            "remote_address",
            None,
        ),
    )

    # -----------------------------------------------------------------------
    # Register browser
    # -----------------------------------------------------------------------

    with browser_ws_lock:
        browser_ws = ws

    try:

        # -------------------------------------------------------------------
        # ROS -> browser send loop
        # -------------------------------------------------------------------

        async def send_loop():

            while True:

                payload = await message_queue.get()

                try:

                    await ws.send(
                        json.dumps(
                            payload,
                            ensure_ascii=False,
                        )
                    )

                    print(
                        "ROS -> Browser:",
                        payload,
                    )

                except websockets.exceptions.ConnectionClosed:
                    print(
                        "Browser WebSocket closed while sending"
                    )
                    break

                except Exception as exc:
                    print(
                        "WebSocket send error:",
                        exc,
                    )
                    break

        send_task = asyncio.create_task(
            send_loop()
        )

        try:

            # ---------------------------------------------------------------
            # Browser -> ROS
            # ---------------------------------------------------------------

            async for message in ws:

                try:

                    payload = json.loads(
                        message
                    )

                except json.JSONDecodeError as exc:

                    print(
                        "Invalid JSON from browser:",
                        message,
                        exc,
                    )

                    continue

                print(
                    "Browser -> ROS:",
                    payload,
                )

                handle_browser_message(
                    payload
                )

        except websockets.exceptions.ConnectionClosed:

            print(
                "Browser WebSocket closed"
            )

        finally:

            send_task.cancel()

            try:
                await send_task

            except asyncio.CancelledError:
                pass

    except asyncio.CancelledError:
        pass

    except Exception as exc:

        print(
            "WebSocket handler error:",
            exc,
        )

    finally:

        # -------------------------------------------------------------------
        # Clear browser connection
        # -------------------------------------------------------------------

        with browser_ws_lock:

            if browser_ws is ws:
                browser_ws = None

        print(
            "Browser disconnected"
        )


# ---------------------------------------------------------------------------
# WebSocket server
# ---------------------------------------------------------------------------

async def ws_server():

    print(
        "WebSocket server listening on "
        "ws://0.0.0.0:9001"
    )

    async with websockets.serve(
        ws_handler,
        "0.0.0.0",
        9001,
    ):

        await asyncio.Future()


# ---------------------------------------------------------------------------
# ROS2 thread
# ---------------------------------------------------------------------------

def ros_thread():

    rclpy.init()

    node = VizijFaceBridge()

    try:

        rclpy.spin(
            node
        )

    except KeyboardInterrupt:
        pass

    finally:

        node.destroy_node()

        rclpy.shutdown()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    global asyncio_loop
    global message_queue

    # -----------------------------------------------------------------------
    # Create asyncio loop
    # -----------------------------------------------------------------------

    asyncio_loop = asyncio.new_event_loop()

    asyncio.set_event_loop(
        asyncio_loop
    )

    # -----------------------------------------------------------------------
    # Create message queue
    # -----------------------------------------------------------------------

    message_queue = asyncio.Queue()

    # -----------------------------------------------------------------------
    # Start ROS2 thread
    # -----------------------------------------------------------------------

    threading.Thread(
        target=ros_thread,
        daemon=True,
    ).start()

    # -----------------------------------------------------------------------
    # Run WebSocket server
    # -----------------------------------------------------------------------

    try:

        asyncio_loop.run_until_complete(
            ws_server()
        )

    except KeyboardInterrupt:
        pass

    finally:

        asyncio_loop.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()