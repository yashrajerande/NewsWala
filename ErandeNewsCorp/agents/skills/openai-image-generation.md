# Skill: OpenAI Image Generation

Generate images using the OpenAI Images API (gpt-image-1 or dall-e-3).

## How it works
1. Load style prefix from line 1 of instructions.md
2. Load model settings (model / size / quality) from instructions.md
3. Prepend style prefix to the incoming image prompt
4. Call openai.images.generate() with the assembled prompt and settings
5. Return the image URL for Telegram to send as a photo

## Model options

| Model        | Quality  | Size       | Cost/image | Cost/month |
|--------------|----------|------------|------------|------------|
| gpt-image-1  | low      | 1024×1024  | ~$0.011    | ~$0.33     |
| gpt-image-1  | medium   | 1024×1024  | ~$0.042    | ~$1.26  ← default |
| gpt-image-1  | high     | 1024×1024  | ~$0.167    | ~$5.01     |
| dall-e-3     | standard | 1024×1024  | ~$0.040    | ~$1.20     |
| dall-e-3     | hd       | 1024×1024  | ~$0.080    | ~$2.40     |

## Graceful fallback
If OPENAI_API_KEY is not set, the agent skips silently and the text
prompt is sent to Telegram instead (so the user can paste it manually).
The pipeline never crashes due to a missing image.

## Changing the art style
Replace the first line of instructions.md with any style description.
The first line becomes the style prefix prepended to every prompt.

Examples:
  Studio Ghibli watercolour: soft pastel tones, hand-drawn warmth, gentle nature backgrounds.
  Pixar 3D animation: rounded shapes, warm cinematic lighting, expressive eyes.
  Indian miniature painting: rich jewel tones, ornate gold borders, flat perspective.
  Vintage 1960s Indian film poster: bold primary colours, hand-painted look.
