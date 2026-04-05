# Skill: Visual Memory Cue

Design a single charming image concept using a cocker spaniel as a
memory hook that ties directly to the news story.

## Core principle
People remember images, not sentences. The dog is the anchor.
If you can picture the dog doing something from the story, you remember the story.

## Rules
- The dog is ALWAYS a cocker spaniel — never another breed
- The dog's action must connect specifically to THIS story, not generically to "news"
- Maximum 3 visual elements total
- Square 1:1 format (for Telegram / Instagram)
- Warm and whimsical — never dark, scary, or sad
- Simple enough to describe in one sentence

## Design process
1. Identify the single core idea of the story
2. Ask: what would a cocker spaniel physically DO in this situation?
3. Choose 1–2 supporting props that make the scene instantly readable
4. Pick a colour mood that reinforces the story's emotion

## Examples by story type
- Space / ISRO story → spaniel in tiny orange spacesuit, floating, Earth behind
- Economic growth story → spaniel arranging gold coins into a rising staircase
- Science discovery → spaniel in lab coat peering through a giant magnifying glass
- Education reform → spaniel in graduation cap reading an enormous open book
- Climate / environment → spaniel planting a tiny sapling with muddy paws
- Trade / export story → spaniel steering a little wooden boat loaded with crates

## Output schema
{
  "concept": str,
  "visual_elements": [str],
  "colour_mood": str,
  "memory_hook": "dog action = story idea"
}
