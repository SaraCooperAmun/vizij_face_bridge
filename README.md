# Vizij Face Bridge

ROS 2 bridge between the robot's interaction skills and the Vizij web face.

The bridge receives ROS 2 commands for **expressions**, **look-at policies**, and **speech metadata**, and forwards them to the Vizij web interface through a WebSocket connection.

## Requirements

You need:

* ROS 2
* Python 3
* `rclpy`
* `websockets`
* `interaction_skills`
* `communication_skills`
* `vizij-web`

For TTS, you need either:

* `tts_ros`
* `emojivoice_tts`


You also need **vizij-web** running and connected to the bridge.

---

# Running the bridge

Source ROS 2:

```bash
source /opt/ros/jazzy/setup.bash
```

If using a workspace:

```bash
source ~/your_ws/install/setup.bash
```

Run the bridge:

```bash
ros2 run vizij_face_bridge bridge
```

The bridge starts a WebSocket server on:

```text
ws://0.0.0.0:9001
```

The Vizij web interface must connect to this WebSocket.

---

# Expressions

Expressions are sent through:

```text
/skill/set_expression
```

The available expression mappings are:

| ROS expression | Vizij semantic key |
| -------------- | ------------------ |
| `neutral`      | `neutral`          |
| `angry`        | `anger`            |
| `sad`          | `sad`              |
| `happy`        | `happy`            |
| `surprised`    | `surprise`         |
| `tired`        | `sleepy`           |
| `bored`        | `sleepy`           |
| `asleep`       | `sleepy`           |
| `concerned`    | `concerned`        |

The expression arousal is in the range `0.0–1.0`.

If arousal is `0.0`, the bridge uses `0.5`. This is corresponding to the 50% Pose on Vizij. 
We can adjust it as needed. 

## Happy

```bash
ros2 topic pub --once /skill/set_expression interaction_skills/msg/SetExpression "{meta: {caller: '', priority: 0}, expression: {header: {stamp: {sec: 0, nanosec: 0}, frame_id: ''}, expression: 'happy', valence: 0.0, arousal: 0.0, confidence: 0.0}, arousal: 0.5}"
```

## Sad

```bash
ros2 topic pub --once /skill/set_expression interaction_skills/msg/SetExpression "{meta: {caller: '', priority: 0}, expression: {header: {stamp: {sec: 0, nanosec: 0}, frame_id: ''}, expression: 'sad', valence: 0.0, arousal: 0.0, confidence: 0.0}, arousal: 0.5}"
```

## Surprised

```bash
ros2 topic pub --once /skill/set_expression interaction_skills/msg/SetExpression "{meta: {caller: '', priority: 0}, expression: {header: {stamp: {sec: 0, nanosec: 0}, frame_id: ''}, expression: 'surprised', valence: 0.0, arousal: 0.0, confidence: 0.0}, arousal: 0.5}"
```

## Angry

```bash
ros2 topic pub --once /skill/set_expression interaction_skills/msg/SetExpression "{meta: {caller: '', priority: 0}, expression: {header: {stamp: {sec: 0, nanosec: 0}, frame_id: ''}, expression: 'angry', valence: 0.0, arousal: 0.0, confidence: 0.0}, arousal: 0.5}"
```

---

# Look At

Look-at behavior is controlled through the `LookAt` action:

```text
/skill/look_at
```

Action type:

```text
interaction_skills/action/LookAt
```

Look-at behavior is controlled using **policies**.

Policies can be used without a target (look at a specified point), or with a target when the policy requires one.

## Run a policy

For example, to run the `idle` gaze policy:

```bash
ros2 action send_goal /skill/look_at interaction_skills/action/LookAt "{policy: 'idle'}"
```

If using the Vizij Web demo, this will enable the idle gaze movement.
To deactivate it change to any other policy:

```bash
ros2 action send_goal /skill/look_at interaction_skills/action/LookAt "{policy: 'reset'}"
```

## Look at a specific point

A target can be provided using a `PointStamped` target:

```bash
ros2 action send_goal /robot_face/look_at   interaction_skills/action/LookAt   "{target: {header: {frame_id: 'base_link'}, point: {x: 0.3, y: 0.1, z: 1.0}}}"
```

The target coordinates are:

```text
x = 1.0
y = 0.0
z = 0.0
```

and the target frame is:

```text
base_link
```

In Emy robot, we had policies like "social" that enabled setting as target the TF of a person - future work. 

---

# Visemes

Visemes can be enabled or disabled through:

```text
/vizij/set_visemes_enabled
```

Service type:

```text
std_srvs/srv/SetBool
```

## Enable visemes

```bash
ros2 service call /vizij/set_visemes_enabled std_srvs/srv/SetBool "{data: true}"
```

## Disable visemes

```bash
ros2 service call /vizij/set_visemes_enabled std_srvs/srv/SetBool "{data: false}"
```

---

# TTS

TTS is handled by a separate TTS node/package (emojivoice\_tts or tts\_node).

The bridge listens to:

```text
/tts/speech
```

with message type:

```text
std_msgs/msg/String
```

The message contains JSON with the generated text and audio duration:

```json
{
  "text": "Hello, how are you?",
  "duration": 1.42
}
```

The bridge forwards this information to Vizij so that the browser can synchronize the face/viseme animation with the generated speech duration.

For TTS, you need either:

* `tts_ros`
* `emojivoice_tts`


You also need **vizij-web** running.

## Say something

Once the TTS node is running:

```bash
ros2 action send_goal /skill/say communication_skills/action/Say "{input: '<emotion(happiness)>hello my name is Emy'}"
```

The `/skill/say` action is handled by the TTS node. The face bridge does not generate or play the audio.

---

# WebSocket

The bridge runs a WebSocket server on:

```text
ws://0.0.0.0:9001
```

The **vizij-web** frontend connects to this WebSocket.

ROS 2 commands are converted into JSON messages and forwarded to the browser.

### Expression

```json
{
  "type": "pose",
  "semanticKey": "happy",
  "value": 0.5
}
```

### Look At

```json
{
  "type": "gaze",
  "policy": "idle"
}
```

When a target is provided:

```json
{
  "type": "gaze",
  "policy": "idle",
  "target": {
    "frame_id": "base_link",
    "x": 1.0,
    "y": 0.0,
    "z": 0.0
  }
}
```

### Speech

```json
{
  "type": "say",
  "text": "Hello",
  "duration": 1.42
}
```

---

# Testing

## 1. Start the face bridge

```bash
ros2 run vizij_face_bridge bridge
```

## 2. Start vizij-web

Start **vizij-web** demo, with only web:

```text
pnpm run dev:demo-ros4hri-face --host
```

With Tauri, opening the face in a separate native window (note that in the robot due to WebKit dependency Tauri does not work). 

```bash
cd ~/vizij_project/vizij-web/apps/demo-ros4hri-face
pnpm tauri dev
```

Tauri starts the Vite development server and displays the face in a separate Tauri window instead of opening it in Firefox.

## 3. Start TTS (if desired)

For example, Coqui TTS:

```text
ros2 run tts_ros tts_node
```

## 4. Test an expression

```bash
ros2 topic pub --once /skill/set_expression interaction_skills/msg/SetExpression "{meta: {caller: '', priority: 0}, expression: {header: {stamp: {sec: 0, nanosec: 0}, frame_id: ''}, expression: 'happy', valence: 0.0, arousal: 0.0, confidence: 0.0}, arousal: 0.5}"
```

## 4. Test Look At

Run the `idle` policy:

```bash
ros2 action send_goal /skill/look_at interaction_skills/action/LookAt "{policy: 'idle'}"
```

Run the policy with a target:

```bash
ros2 action send_goal /skill/look_at interaction_skills/action/LookAt "{target: {header: {stamp: {sec: 0, nanosec: 0}, frame_id: 'base_link'}, point: {x: 1.0, y: 0.0, z: 0.0}}}"
```

Reset the policy:

```bash
ros2 action send_goal /skill/look_at interaction_skills/action/LookAt "{policy: 'reset'}"
```

## 5. Enable visemes

```bash
ros2 service call /vizij/set_visemes_enabled std_srvs/srv/SetBool "{data: true}"
```

## 6. Test speech

Make sure `tts_ros` or `emojivoice_tts` is running:

```bash
ros2 action send_goal /skill/say communication_skills/action/Say "{input: '<emotion(happiness)>hello my name is Emy'}"
```