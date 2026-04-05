# Skill: Tintin Type Image

Convert an image idea into a Franco-Belgian clear-line comic prompt
for OpenAI image generation.

## When to use
- Tintin-like visual feel
- Classic European / Franco-Belgian comics
- Ligne claire / clean-line comic art
- Retro adventure illustration with flat colors

## Style attributes
Always express style through visual attributes, not just artist names:

- classic Franco-Belgian clear-line comic illustration
- uniform, crisp black contour lines
- flat, opaque color fills
- minimal gradients
- minimal rendering and texture
- very limited shadows
- clean, balanced compositions
- expressive but simplified faces
- readable hands and body language
- lightly detailed backgrounds
- whimsical mid-20th-century adventure tone
- polished print-comic appearance
- no photorealism
- no painterly brushwork
- no manga conventions
- no 3D-render look

## Prompt construction order
1. Main subject and action
2. Setting and era cues
3. Composition / camera angle
4. Style block
5. Lighting block
6. Quality / cleanliness block
7. Exclusions

## Prompt pattern
"Create an illustrated scene of [subject/action] in [setting].
Composition: [framing/angle].
Visual style: classic European clear-line adventure comic, crisp uniform
ink outlines, flat color fills, minimal shading, simplified but expressive
faces, clean mid-century comic aesthetic, highly readable storytelling,
polished print-comic finish.
Lighting: bright, even, natural light.
Avoid photorealism, painterly texture, heavy shadows, messy sketch lines,
anime styling, exaggerated musculature, 3D rendering, text artifacts,
distorted hands."

## Example

**Input:** A young reporter and a white dog running through an old port city chasing smugglers

**Output prompt:**
Create an illustrated scene of a brave young reporter in a tan trench coat
running through an old European port with a small white terrier beside him
as they chase smugglers through stacked crates and narrow alleys.
Composition: dynamic three-quarter action shot, medium-wide framing,
strong forward motion.
Visual style: classic European clear-line adventure comic, crisp uniform
black ink outlines, flat color fills, minimal shading, simplified but
expressive faces, clean architectural details, polished mid-century
comic-book storytelling aesthetic.
Lighting: bright daytime coastal light.
Keep the image elegant, readable, and uncluttered.
Avoid photorealism, painterly texture, gritty realism, anime styling,
3D-render effects, excessive shadows, text, logos, and distorted anatomy.

**Avoid:** photorealistic, painterly, messy sketching, heavy texture,
deep chiaroscuro, anime eyes, cinematic blur, 3D CGI, text artifacts

## Suggested OpenAI settings
- model: gpt-image-1
- size: 1024x1024
- quality: medium
