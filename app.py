
from pathlib import Path
import gradio as gr

from video_maker import create_video, TRANSITIONS


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TRANSITION_OPTIONS = ["Cut", *TRANSITIONS.keys()]
TRANSITION_OPTIONS = list(dict.fromkeys(TRANSITION_OPTIONS))


def generate_video(
    reference_audio,
    aspect_ratio,
    transition_mode,
    global_transition,
    transition_seconds,
    show_subtitles,
    *scene_values,
):
    """Collect the scene fields and create the complete video."""
    scenes = []

    # Every scene contributes four values:
    # image, narration text, minimum duration, transition into this scene.
    for index in range(8):
        offset = index * 4

        image_path = scene_values[offset]
        narration = scene_values[offset + 1]
        duration = scene_values[offset + 2]
        transition = scene_values[offset + 3]

        # Ignore a scene that the user has not started filling in.
        if not image_path and not (narration or "").strip():
            continue

        scenes.append({
            "image": image_path,
            "narration": narration or "",
            "duration": duration or 0,
            "transition": transition or "Fade",
        })

    try:
        video_path = create_video(
            scenes=scenes,
            reference_upload=reference_audio,
            aspect_ratio=aspect_ratio,
            transition_mode=transition_mode,
            global_transition=global_transition,
            transition_seconds=transition_seconds,
            show_subtitles=show_subtitles,
        )

        return video_path, (
            "Video generated successfully. "
            "The narration was generated from your scene text."
        )

    except Exception as error:
        return None, f"Video generation failed:\n{error}"


with gr.Blocks(title="AI Video Maker with Your Voice") as app:
    gr.Markdown(
        """
        # AI Video Maker with Your Own Voice

        Upload your voice reference once. Each scene's narration text will
        be spoken in a voice resembling that recording. The original words
        in the reference recording are not used as the scene narration.

        **Note:** This version generates English narration locally on your CPU.
        The first run downloads the voice model and can take a while.
        """
    )

    with gr.Row():
        reference_audio = gr.Audio(
            label="Reference voice recording (upload once)",
            type="filepath",
        )

    gr.Markdown(
        "Use a clear recording of your own voice, ideally with little "
        "background noise. Leave this field empty on later runs to reuse "
        "your saved reference."
    )

    with gr.Row():
        aspect_ratio = gr.Radio(
            choices=[
                "Vertical (9:16)",
                "Landscape (16:9)",
            ],
            value="Vertical (9:16)",
            label="Video format",
        )

        show_subtitles = gr.Checkbox(
            value=True,
            label="Display narration as subtitles",
        )

    with gr.Accordion("Transition settings", open=True):
        transition_mode = gr.Radio(
            choices=[
                "Use scene settings",
                "Same transition for all",
                "Random",
            ],
            value="Use scene settings",
            label="Transition mode",
        )

        global_transition = gr.Dropdown(
            choices=TRANSITION_OPTIONS,
            value="Fade",
            label="Transition to use for all scenes",
        )

        transition_seconds = gr.Slider(
            minimum=0.1,
            maximum=2.0,
            value=0.5,
            step=0.1,
            label="Transition duration (seconds)",
        )

    scene_inputs = []

    for number in range(1, 9):
        with gr.Accordion(f"Scene {number}", open=(number == 1)):
            image_input = gr.Image(
                type="filepath",
                label=f"Scene {number} image",
            )

            narration_input = gr.Textbox(
                lines=3,
                label=f"Scene {number} narration text / subtitles",
                placeholder=(
                    "Enter the exact new words you want the voice to speak."
                ),
            )

            duration_input = gr.Slider(
                minimum=0,
                maximum=120,
                value=0,
                step=1,
                label=(
                    "Minimum scene duration in seconds "
                    "(0 = automatically use the narration length)"
                ),
            )

            transition_input = gr.Dropdown(
                choices=TRANSITION_OPTIONS,
                value="Fade",
                label=f"Transition into scene {number}",
            )

            scene_inputs.extend([
                image_input,
                narration_input,
                duration_input,
                transition_input,
            ])

    generate_button = gr.Button(
        "Generate Complete Video",
        variant="primary",
    )

    output_video = gr.Video(label="Finished video")
    status = gr.Textbox(label="Status", interactive=False)

    generate_button.click(
        fn=generate_video,
        inputs=[
            reference_audio,
            aspect_ratio,
            transition_mode,
            global_transition,
            transition_seconds,
            show_subtitles,
            *scene_inputs,
        ],
        outputs=[output_video, status],
    )


if __name__ == "__main__":
    app.launch()

# import os
# import gradio as gr

# from video_maker import create_video, TRANSITION_NAMES

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
# os.makedirs(OUTPUT_DIR, exist_ok=True)

# MAX_SCENES = 8


# def generate_video(
#     video_format,
#     zoom_effect,
#     default_voice,
#     transition_mode,
#     transition_type,
#     transition_duration,
#     *scene_values,
# ):
#     scenes = []

#     for i in range(MAX_SCENES):
#         (
#             image_path,
#             script,
#             scene_voice,
#             duration,
#             scene_transition,
#         ) = scene_values[i * 5:(i + 1) * 5]

#         # A scene-specific recording takes priority over shared audio.
#         chosen_voice = scene_voice or default_voice

#         if image_path and script and script.strip() and chosen_voice:
#             scenes.append(
#                 {
#                     "image_path": image_path,
#                     "script": script.strip(),
#                     "uploaded_voice": chosen_voice,
#                     "duration": float(duration or 0),
#                     "transition_to_next": scene_transition or "Fade",
#                 }
#             )

#         elif image_path or (script and script.strip()) or scene_voice:
#             raise gr.Error(
#                 f"Scene {i + 1}: provide an image and narration text, "
#                 "and either use the shared audio or upload a recording "
#                 "for this scene. Leave unused scenes completely empty."
#             )

#     if not scenes:
#         raise gr.Error(
#             "Add at least one scene with an image and narration text."
#         )

#     if not default_voice and not any(
#         scene.get("uploaded_voice") for scene in scenes
#     ):
#         raise gr.Error(
#             "Upload a shared narration audio file, or upload a recording "
#             "for each scene you want to use."
#         )

#     try:
#         output_path = create_video(
#             scenes=scenes,
#             output_dir=OUTPUT_DIR,
#             video_format=video_format,
#             zoom_effect=zoom_effect,
#             transition_mode=transition_mode,
#             transition_type=transition_type,
#             transition_duration=transition_duration,
#         )

#         return output_path, output_path

#     except Exception as exc:
#         raise gr.Error(f"Video creation failed: {exc}") from exc


# with gr.Blocks(
#     title="Local Multi-Scene Video Maker",
#     theme=gr.themes.Soft(),
# ) as demo:

#     gr.Markdown(
#         "# Local Multi-Scene Video Maker\n"
#         "Create a narrated video from up to 8 images using audio files "
#         "from your computer. Use one shared narration file or upload "
#         "a different recording for individual scenes. No API key or "
#         "online voice service is required."
#     )

#     with gr.Tab("Storyboard"):
#         gr.Markdown("## Shared narration audio")

#         shared_voice = gr.Audio(
#             label="Upload common narration audio (used by all scenes by default)",
#             type="filepath",
#             sources=["upload", "microphone"],
#         )

#         gr.Markdown(
#             "Upload one audio file here to use it as the default for every "
#             "scene. To replace it for a particular scene, upload a recording "
#             "in that scene. Narration text is used for subtitles only."
#         )

#         scene_components = []

#         for i in range(MAX_SCENES):
#             with gr.Accordion(
#                 f"Scene {i + 1}",
#                 open=(i == 0),
#             ):
#                 with gr.Row():
#                     with gr.Column():
#                         img = gr.Image(
#                             type="filepath",
#                             label=f"Scene {i + 1} image",
#                             sources=["upload"],
#                         )

#                         script = gr.Textbox(
#                             label="Narration text / subtitles",
#                             lines=4,
#                             placeholder=(
#                                 "Enter the words spoken in this scene "
#                                 "so captions can be shown."
#                             ),
#                         )

#                     with gr.Column():
#                         audio = gr.Audio(
#                             label=(
#                                 "Optional recording for this scene "
#                                 "(overrides shared audio)"
#                             ),
#                             type="filepath",
#                             sources=["upload", "microphone"],
#                         )

#                         duration = gr.Number(
#                             value=0,
#                             minimum=0,
#                             label=(
#                                 "Extra minimum scene duration in seconds "
#                                 "(0 = automatic)"
#                             ),
#                         )

#                         scene_transition = gr.Dropdown(
#                             choices=TRANSITION_NAMES,
#                             value="Fade",
#                             label="Transition from this scene to the next",
#                             info=(
#                                 "Used in Per-scene mode. The last scene's "
#                                 "transition is ignored."
#                             ),
#                         )

#                 scene_components.extend(
#                     [
#                         img,
#                         script,
#                         audio,
#                         duration,
#                         scene_transition,
#                     ]
#                 )

#     with gr.Tab("Video settings"):
#         video_format = gr.Radio(
#             choices=[
#                 "Vertical 9:16 (TikTok/Reels)",
#                 "Landscape 16:9 (YouTube)",
#             ],
#             value="Vertical 9:16 (TikTok/Reels)",
#             label="Video format",
#         )

#         zoom_effect = gr.Checkbox(
#             value=True,
#             label="Gentle background zoom effect",
#             info=(
#                 "Zooms the blurred background. The complete original "
#                 "image remains visible."
#             ),
#         )

#         gr.Markdown("## Scene transitions")

#         transition_mode = gr.Radio(
#             choices=[
#                 "Per-scene",
#                 "Same transition for all",
#                 "Random transitions",
#             ],
#             value="Per-scene",
#             label="Transition selection mode",
#             info=(
#                 "Per-scene uses the dropdown inside each scene. "
#                 "Same transition for all applies one selected effect "
#                 "to every scene boundary. Random selects effects automatically."
#             ),
#         )

#         transition_type = gr.Dropdown(
#             choices=TRANSITION_NAMES,
#             value="Crossfade",
#             label="Transition to apply to all scenes",
#             info="Used when Same transition for all is selected.",
#         )

#         transition_duration = gr.Slider(
#             minimum=0.1,
#             maximum=2.0,
#             value=0.7,
#             step=0.1,
#             label="Transition duration (seconds)",
#             info=(
#                 "Longer transitions overlap scenes for longer. "
#                 "Very short scenes may need shorter transitions."
#             ),
#         )

#     make = gr.Button(
#         "Generate narrated MP4",
#         variant="primary",
#     )

#     with gr.Row():
#         video = gr.Video(label="Preview")
#         download = gr.File(label="Download MP4")

#     make.click(
#         fn=generate_video,
#         inputs=[
#             video_format,
#             zoom_effect,
#             shared_voice,
#             transition_mode,
#             transition_type,
#             transition_duration,
#             *scene_components,
#         ],
#         outputs=[video, download],
#     )


# if __name__ == "__main__":
#     demo.queue().launch(
#         server_name="127.0.0.1",
#         server_port=7860,
#         inbrowser=True,
#         share=False,
#     )


# # import os
# # import gradio as gr
# # from video_maker import create_video

# # BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# # OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
# # os.makedirs(OUTPUT_DIR, exist_ok=True)
# # MAX_SCENES = 8


# # def generate_video(video_format, zoom_effect, default_voice, *scene_values):
# #     scenes = []

# #     for i in range(MAX_SCENES):
# #         image_path, script, scene_voice, duration = scene_values[i * 4:(i + 1) * 4]
# #         # A scene-specific recording takes priority. If none is supplied,
# #         # the shared voice audio selected once above is used for this scene.
# #         chosen_voice = scene_voice or default_voice

# #         if image_path and script and script.strip() and chosen_voice:
# #             scenes.append({
# #                 "image_path": image_path,
# #                 "script": script.strip(),
# #                 "uploaded_voice": chosen_voice,
# #                 "duration": float(duration or 0),
# #             })
# #         elif image_path or (script and script.strip()) or scene_voice:
# #             raise gr.Error(
# #                 f"Scene {i + 1}: provide an image and narration text, and either use the shared audio "
# #                 "or upload a recording for this scene. Leave unused scenes completely empty."
# #             )

# #     if not scenes:
# #         raise gr.Error("Add at least one scene with an image and narration text.")
# #     if not default_voice and not any(scene.get("uploaded_voice") for scene in scenes):
# #         raise gr.Error("Upload a shared narration audio file, or upload a recording for each scene you want to use.")

# #     try:
# #         output_path = create_video(
# #             scenes=scenes,
# #             output_dir=OUTPUT_DIR,
# #             video_format=video_format,
# #             zoom_effect=zoom_effect,
# #         )
# #         return output_path, output_path
# #     except Exception as exc:
# #         raise gr.Error(f"Video creation failed: {exc}")


# # with gr.Blocks(title="Local Multi-Scene Video Maker", theme=gr.themes.Soft()) as demo:
# #     gr.Markdown(
# #         "# Local Multi-Scene Video Maker\n"
# #         "Create a narrated video from up to 8 images using audio files from your computer. "
# #         "Upload one shared narration audio file to use it for every scene, or add an optional "
# #         "scene-specific recording to replace it for that scene. No API key or online voice service is required."
# #     )

# #     with gr.Tab("Storyboard"):
# #         gr.Markdown("## Shared narration audio")
# #         shared_voice = gr.Audio(
# #             label="Upload common narration audio (used by all scenes by default)",
# #             type="filepath",
# #             sources=["upload", "microphone"],
# #         )
# #         gr.Markdown(
# #             "Upload one audio file here to use it as the default for every scene. "
# #             "If you have a separate recording for a particular scene, upload it in that scene below; "
# #             "it will override the shared audio for that scene. The narration text is used for subtitles only."
# #         )

# #         scene_components = []
# #         for i in range(MAX_SCENES):
# #             with gr.Accordion(f"Scene {i + 1}", open=(i == 0)):
# #                 with gr.Row():
# #                     with gr.Column():
# #                         img = gr.Image(type="filepath", label=f"Scene {i + 1} image", sources=["upload"])
# #                         script = gr.Textbox(
# #                             label="Narration text / subtitles",
# #                             lines=4,
# #                             placeholder="Enter the words spoken in this scene so captions can be shown.",
# #                         )
# #                     with gr.Column():
# #                         audio = gr.Audio(
# #                             label="Optional recording for this scene (overrides shared audio)",
# #                             type="filepath",
# #                             sources=["upload", "microphone"],
# #                         )
# #                         duration = gr.Number(
# #                             value=0,
# #                             minimum=0,
# #                             label="Extra minimum scene duration in seconds (0 = automatic)",
# #                         )
# #                 scene_components.extend([img, script, audio, duration])

# #     with gr.Tab("Video settings"):
# #         video_format = gr.Radio(
# #             choices=["Vertical 9:16 (TikTok/Reels)", "Landscape 16:9 (YouTube)"],
# #             value="Vertical 9:16 (TikTok/Reels)",
# #             label="Video format",
# #         )
# #         zoom_effect = gr.Checkbox(value=True, label="Gentle zoom effect")

# #     make = gr.Button("Generate narrated MP4", variant="primary")
# #     with gr.Row():
# #         video = gr.Video(label="Preview")
# #         download = gr.File(label="Download MP4")

# #     make.click(
# #         fn=generate_video,
# #         inputs=[video_format, zoom_effect, shared_voice, *scene_components],
# #         outputs=[video, download],
# #     )

# # if __name__ == "__main__":
# #     demo.queue().launch(server_name="127.0.0.1", server_port=7860, inbrowser=True, share=False)
