# Vizij Face Bridge

ROS 2 bridge between the robot's interaction skills and the Vizij web face.

The bridge receives ROS 2 commands for **expressions**, **gaze**, **mouth modes**, **speech metadata**, and **visemes**, and forwards them to the Vizij web interface through a WebSocket connection.

---

# Requirements

You need:

* ROS 2
* Python 3
* `rclpy`
* `websockets`
* `interaction_skills`
* `communication_skills`
* `hri_msgs`
* `vizij-web`

For TTS, you can use either:

* `coqui_tts`
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

Expressions are received through:

```text
/skill/set_expression
```

with message type:

```text
interaction_skills/msg/SetExpression
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

If arousal is `0.0`, the bridge uses `0.5`, corresponding to 50% expression intensity in Vizij.

This value can be adjusted as needed.

## Happy

```bash
ros2 topic pub --once /skill/set_expression interaction_skills/msg/SetExpression "{meta: {caller: '', priority: 0}, expression: {header: {stamp: {sec: 0, nanosec: 0}, frame_id: ''}, expression: 'happy', valence: 0.0, arousal: 0.5, confidence: 0.0}}"
```

## Sad

```bash
ros2 topic pub --once /skill/set_expression interaction_skills/msg/SetExpression "{meta: {caller: '', priority: 0}, expression: {header: {stamp: {sec: 0, nanosec: 0}, frame_id: ''}, expression: 'sad', valence: 0.0, arousal: 0.5, confidence: 0.0}}"
```

## Surprised

```bash
ros2 topic pub --once /skill/set_expression interaction_skills/msg/SetExpression "{meta: {caller: '', priority: 0}, expression: {header: {stamp: {sec: 0, nanosec: 0}, frame_id: ''}, expression: 'surprised', valence: 0.0, arousal: 0.5, confidence: 0.0}}"
```

## Angry

```bash
ros2 topic pub --once /skill/set_expression interaction_skills/msg/SetExpression "{meta: {caller: '', priority: 0}, expression: {header: {stamp: {sec: 0, nanosec: 0}, frame_id: ''}, expression: 'angry', valence: 0.0, arousal: 0.5, confidence: 0.0}}"
```

---

# Look At

Look-at behavior is controlled through the `LookAt` action:

```text
/robot_face/look_at
```

Action type:

```text
interaction_skills/action/LookAt
```

Look-at behavior is controlled using **policies**.

Policies can be used without a target, or with a target when the policy requires one.

## Run a policy

For example, to run the `idle` gaze policy:

```bash
ros2 action send_goal /robot_face/look_at interaction_skills/action/LookAt "{policy: 'idle'}"
```

To deactivate the current gaze behavior:

```bash
ros2 action send_goal /robot_face/look_at interaction_skills/action/LookAt "{policy: 'reset'}"
```

## Look at a specific point

A target can be provided using a `PointStamped` target:

```bash
ros2 action send_goal /robot_face/look_at interaction_skills/action/LookAt "{target: {header: {frame_id: 'base_link'}, point: {x: 0.3, y: 0.1, z: 1.0}}}"
```

The target coordinates are expressed in the specified frame.

In the Emy robot, policies such as `social` were also used to enable a person detected through TF to become the gaze target. This is future work for the current bridge.

---

# Mouth Modes

The Vizij face bridge provides a ROS 2 service for changing the mouth animation mode:

```bash
ros2 service call /vizij/set_mouth_mode hri_msgs/srv/SetMouthMode "{mode: 'MODE'}"
```

Supported modes are:

* `static` — keeps the mouth in its static/default state.
* `hidden` — hides the mouth.
* `lipsync` — enables lip-sync using the incoming `/tts/visemes` stream.
* `open_close` — alternates the mouth between open and closed states.

## Examples

Set the mouth to static:

```bash
ros2 service call /vizij/set_mouth_mode hri_msgs/srv/SetMouthMode "{mode: 'static'}"
```

Hide the mouth:

```bash
ros2 service call /vizij/set_mouth_mode hri_msgs/srv/SetMouthMode "{mode: 'hidden'}"
```

Enable lip-sync:

```bash
ros2 service call /vizij/set_mouth_mode hri_msgs/srv/SetMouthMode "{mode: 'lipsync'}"
```

Enable open/close animation:

```bash
ros2 service call /vizij/set_mouth_mode hri_msgs/srv/SetMouthMode "{mode: 'open_close'}"
```

The bridge validates the requested mode and forwards it to the Vizij browser through WebSocket:

```json
{
  "type": "mouth_mode",
  "mode": "lipsync"
}
```

Check that the service is available:

```bash
ros2 service list | grep mouth
```

Inspect its interface:

```bash
ros2 interface show hri_msgs/srv/SetMouthMode
```

Expected interface:

```text
string mode
---
bool success
string message
```

A successful call returns:

```text
success: true
message: Mouth mode set to lipsync
```

---

# TTS

TTS is handled by a separate TTS node/package. Two implementations are supported:

* `coqui_tts`
* `emojivoice_tts`

Both provide the same interfaces to the face bridge.

The face bridge subscribes to:

```text
/tts/speech
/tts/visemes
```

## Speech

`/tts/speech` uses:

```text
std_msgs/msg/String
```

and contains JSON with the generated text and audio duration:

```json
{
  "text": "Hello, how are you?",
  "duration": 1.42
}
```

The bridge forwards this information to Vizij through WebSocket:

```json
{
  "type": "say",
  "text": "Hello, how are you?",
  "duration": 1.42
}
```

The browser uses the speech information to synchronize the face animation with the generated speech.

## Visemes

`/tts/visemes` uses:

```text
hri_msgs/msg/Visemes
```

The TTS node publishes the visemes progressively while the generated audio is being played.

Each `Visemes` message contains one or more `Viseme` messages. The bridge reads the first viseme:

```python
viseme = msg.visemes[0]
```

and converts its ROS4HRI numeric value into the corresponding Vizij viseme name.

The current mapping is:

| ROS4HRI value | ROS4HRI viseme | Vizij viseme |
| ------------: | -------------- | ------------ |
|             0 | SIL            | `sil`        |
|             1 | PP             | `p`          |
|             2 | FF             | `f`          |
|             3 | TH             | `t_2`        |
|             4 | DD             | `t`          |
|             5 | KK             | `k`          |
|             6 | CH             | `t_2`        |
|             7 | SS             | `s`          |
|             8 | NN             | `n`          |
|             9 | RR             | `r`          |
|            10 | AA             | `a`          |
|            11 | E              | `e`          |
|            12 | IH             | `i`          |
|            13 | OH             | `o`          |
|            14 | OU             | `u`          |

For example, a ROS4HRI `OH` viseme:

```text
value: 13
```

is converted by the bridge to:

```json
{
  "type": "viseme",
  "value": "o"
}
```

and sent to the Vizij browser through WebSocket.

Therefore, the complete TTS/viseme flow is:

```text
TTS node
   │
   ├── /tts/speech ──────────────► Vizij Face Bridge
   │                                  │
   │                                  └──► WebSocket "say"
   │
   └── /tts/visemes ─────────────► Vizij Face Bridge
                                      │
                                      └──► ROS4HRI → Vizij mapping
                                           │
                                           └──► WebSocket "viseme"
```

The TTS node is responsible for **generating the audio and determining the viseme sequence**. The bridge does not generate visemes; it translates the ROS4HRI viseme values into the Vizij vocabulary and forwards them to the browser.

Both TTS implementations should publish the same `/tts/speech` and `/tts/visemes` interfaces so that the face bridge remains independent of the specific TTS implementation.

---

# Say Something

The `/tts/say` action is handled by the TTS node.

For example, with Coqui TTS:

```bash
ros2 launch coqui_tts coqui.launch
```

Then a speech request can be sent with:

```bash
ros2 action send_goal /tts/say communication_skills/action/Say "{input: '<set expression(happy)>hello my name is Emy</expression>'}"
```

The TTS node is responsible for generating and playing the audio and publishing the corresponding speech metadata and visemes.

The face bridge does not generate or play audio.

Higher-level speech management can also be handled by the `dialogue_manager`.

---

# WebSocket

The bridge runs a WebSocket server on:

```text
ws://0.0.0.0:9001
```

The **vizij-web** frontend connects to this WebSocket.

ROS 2 commands are converted into JSON messages and forwarded to the browser.

## Expression

```json
{
  "type": "pose",
  "semanticKey": "happy",
  "value": 0.5
}
```

## Look At

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
    "x": 0.3,
    "y": 0.1,
    "z": 1.0
  }
}
```

## Mouth Mode

```json
{
  "type": "mouth_mode",
  "mode": "lipsync"
}
```

## Speech

```json
{
  "type": "say",
  "text": "Hello",
  "duration": 1.42
}
```

## Viseme

```json
{
  "type": "viseme",
  "value": "o"
}
```

---

# Testing

## 1. Start the face bridge

```bash
ros2 run vizij_face_bridge bridge
```

## 2. Start vizij-web

Start the **vizij-web** demo using only the web interface:

```bash
pnpm run dev:demo-ros4hri-face --host
```

With Tauri, the face can be opened in a separate native window. Note that Tauri does not currently work on the robot due to the WebKit dependency.

```bash
cd ~/vizij_project/vizij-web/apps/demo-ros4hri-face
pnpm tauri dev
```

Tauri starts the Vite development server and displays the face in a separate Tauri window instead of opening it in Firefox.

## 3. Start TTS

### Coqui TTS

```bash
ros2 launch coqui_tts coqui.launch
```

### EmojiVoice TTS

Start the `emojivoice_tts` node using its corresponding launch configuration.

Only one TTS implementation needs to be running at a time.

## 4. Test an expression

```bash
ros2 topic pub --once /skill/set_expression interaction_skills/msg/SetExpression "{meta: {caller: '', priority: 0}, expression: {header: {stamp: {sec: 0, nanosec: 0}, frame_id: ''}, expression: 'happy', valence: 0.0, arousal: 0.5, confidence: 0.0}}"
```

## 5. Test Look At

Run the `idle` policy:

```bash
ros2 action send_goal /robot_face/look_at interaction_skills/action/LookAt "{policy: 'idle'}"
```

Run the policy with a target:

```bash
ros2 action send_goal /robot_face/look_at interaction_skills/action/LookAt "{target: {header: {stamp: {sec: 0, nanosec: 0}, frame_id: 'base_link'}, point: {x: 1.0, y: 0.0, z: 0.0}}}"
```

Reset the policy:

```bash
ros2 action send_goal /robot_face/look_at interaction_skills/action/LookAt "{policy: 'reset'}"
```

## 6. Set mouth mode

For viseme-based lip-sync:

```bash
ros2 service call /vizij/set_mouth_mode hri_msgs/srv/SetMouthMode "{mode: 'lipsync'}"
```

For open/close mouth animation:

```bash
ros2 service call /vizij/set_mouth_mode hri_msgs/srv/SetMouthMode "{mode: 'open_close'}"
```

## 7. Test speech

Make sure either `coqui_tts` or `emojivoice_tts` is running.

For example:

```bash
ros2 action send_goal /tts/say communication_skills/action/Say "{input: '<set expression(happy)>hello my name is Emy</expression>'}"
```

For lip-sync, make sure the mouth mode is set to:

```bash
ros2 service call /vizij/set_mouth_mode hri_msgs/srv/SetMouthMode "{mode: 'lipsync'}"
```

The TTS node will publish `/tts/speech` and `/tts/visemes`, and the bridge will forward both to Vizij.
