"""Definitions for the Three Devils, their regions, lore, and heuristics.

Every Devil maps directly to one of the real heuristic models in
``heuristics/evaluation.py`` so that story progression aligns 1-to-1 with AI
evaluation complexity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class HeuristicFeatureSpec:
    """Metadata describing one weighted term of a Devil's evaluation function."""

    name: str
    weight: str
    description: str


@dataclass(frozen=True, slots=True)
class DevilProfile:
    """Complete story, visual, and algorithmic profile for one Devil boss."""

    devil_id: str
    numeral: str
    name: str
    title: str
    region_name: str
    difficulty_label: str
    heuristic_key: str
    heuristic_title: str
    heuristic_formula: str
    heuristic_summary: str
    features: tuple[HeuristicFeatureSpec, ...]
    default_k: int
    accent_hex: str
    scene_image: str
    intro_taunt: str
    score_taunt: str
    flinch_line: str
    defeat_line: str
    victory_taunt: str


STORY_SLIDES: tuple[dict[str, str], ...] = (
    {
        "chapter": "I · THE ANCIENT RITUAL",
        "title": "Older Than the Crown",
        "body": (
            "Long before Nibel had a king, its spirits settled oaths across a carved "
            "seven-column frame. No match ended at the first alignment—every orb had "
            "to fall until the forty-second stone sealed the fate of both souls."
        ),
        "image": "Gemini_Generated_Image_nvp7mnnvp7mnnvp7.jpg",
    },
    {
        "chapter": "II · THE WITHERING",
        "title": "When the Three Devils Came",
        "body": (
            "Out of the storm-split willow crept three ancient Devils: Howl of the "
            "Marsh, Mora of the Mouldwood Web, and Shriek of the Silent Spire. They "
            "twisted the sacred game into a harvest of light."
        ),
        "image": "wallpaperflare.com_wallpaper (3).jpg",
    },
    {
        "chapter": "III · YOUR SISTER'S LIGHT",
        "title": "A Golden Wisp Taken",
        "body": (
            "Your sister challenged Shriek to save the forest sanctuary. Caught in "
            "the owl's merciless window-counting gaze, her light was bound inside "
            "the Spire before the final stone had barely settled."
        ),
        "image": "wallpaperflare.com_wallpaper.jpg",
    },
    {
        "chapter": "IV · YOUR OATH",
        "title": "To the Last Disc",
        "body": (
            "Now you stand before their ritual table carrying the last spirit orbs. "
            "Choose any Devil in any region, outthink their search to the forty-second "
            "stone, cleanse the three blighted lands, and bring your sister home."
        ),
        "image": "Gemini_Generated_Image_7uat4u7uat4u7uat.jpg",
    },
)


DEVILS: tuple[DevilProfile, ...] = (
    DevilProfile(
        devil_id="howl",
        numeral="I",
        name="Howl",
        title="Stalker of the Whispering Marsh",
        region_name="Whispering Marsh",
        difficulty_label="Level I · Feral Predator (Easy)",
        heuristic_key="opportunities",
        heuristic_title="Scoring-Opportunity Heuristic",
        heuristic_formula="eval = raw / (1000 + |raw|),  raw = 100·ΔFours + 20·ΔMoves + 15·ΔBestGain + 5·ΔTotalGain + 2·ΔCenter",
        heuristic_summary=(
            "An impulsive hunter that fixates on immediate bloodshed: completed fours "
            "and legal drops that instantly complete new fours on the very next turn, "
            "without planning multi-stone setups."
        ),
        features=(
            HeuristicFeatureSpec("Completed Fours", "100.0", "Exact 4-in-a-row windows already locked on the board"),
            HeuristicFeatureSpec("Scoring Columns", "20.0", "Count of playable columns that immediately complete ≥1 four"),
            HeuristicFeatureSpec("Best Single Move", "15.0", "Maximum overlapping fours gained by a single legal drop"),
            HeuristicFeatureSpec("Total Immediate Gain", "5.0", "Sum of immediate four gains across all playable columns"),
            HeuristicFeatureSpec("Center Control", "2.0", "Discs occupying central column(s) for broader reach"),
        ),
        default_k=2,
        accent_hex="#4cc9f0",
        scene_image="wallpaperflare.com_wallpaper (2).jpg",
        intro_taunt="Another little wisp steps onto the marsh stones. Drop quickly—my jaws are waiting.",
        score_taunt="Snap! Another four torn from your paws.",
        flinch_line="Grr—that light burns the mire!",
        defeat_line="The marsh mist parts... my shadow fades into the reeds...",
        victory_taunt="Too slow, little light. The swamp keeps what it catches.",
    ),
    DevilProfile(
        devil_id="mora",
        numeral="II",
        name="Mora",
        title="Weaver of the Mouldwood Depths",
        region_name="Mouldwood Depths",
        difficulty_label="Level II · Web Architect (Intermediate)",
        heuristic_key="gravity",
        heuristic_title="Gravity-Aware Heuristic",
        heuristic_formula="eval = raw / (1000 + |raw|),  candidate windows weighted by 0.5^(support moves below)",
        heuristic_summary=(
            "A patient spider queen who understands gravity: she scores open threes "
            "and twos across all 69 windows, but discounts floating threats by 0.5^s "
            "for every empty support cell underneath that must be filled first."
        ),
        features=(
            HeuristicFeatureSpec("Completed Fours", "100.0", "All 4 cells owned in any of the 69 windows"),
            HeuristicFeatureSpec("Gravity Open Threes", "10.0 × 0.5ˢ", "3 discs + 1 empty, discounted per empty support cell below"),
            HeuristicFeatureSpec("Gravity Open Twos", "3.0 × 0.5ˢ", "2 discs + 2 empty, discounted per empty support cell below"),
            HeuristicFeatureSpec("Center Control", "2.0", "Discs anchored in the central column"),
        ),
        default_k=4,
        accent_hex="#80ed99",
        scene_image="OriandtheWilloftheWisps_xbox1_1920x1080_01-1024x576.jpg",
        intro_taunt="Every column is a strand of silk. Drop one stone wrong and you build my web for me.",
        score_taunt="See how your own stone supported my snare?",
        flinch_line="Hsss! You severed a primary thread!",
        defeat_line="The dark silk dissolves... light reaches the cavern floor...",
        victory_taunt="Wrapped tight in forty-two stones. Rest in the dark.",
    ),
    DevilProfile(
        devil_id="shriek",
        numeral="III",
        name="Shriek",
        title="Winged Ruin of the Silent Spire",
        region_name="Silent Spire",
        difficulty_label="Level III · Sister's Captor (Hard / Final Boss)",
        heuristic_key="windows",
        heuristic_title="Full 69-Window GA-Tuned Heuristic",
        heuristic_formula="eval = raw / (1000 + |raw|),  raw = 100·ΔFours + 10·ΔOpen3 + 5·ΔOpen2 + 10·ΔCenter",
        heuristic_summary=(
            "The apex sovereign who took your sister's soul. Tuned via Hill Climbing, "
            "Genetic Algorithm & 64-game K=4 validation (42W–18D–4L): scans all 69 windows "
            "with boosted open-two (5.0) and center-dominance (10.0) weights."
        ),
        features=(
            HeuristicFeatureSpec("Completed Fours", "100.0", "Locked 4-disc lines (including overlapping 5- and 6-in-a-row)"),
            HeuristicFeatureSpec("Open Threes", "10.0", "Unblocked 4-cell windows holding 3 friendly discs + 1 empty"),
            HeuristicFeatureSpec("Open Twos (GA-Tuned)", "5.0", "Unblocked 4-cell windows holding 2 friendly discs + 2 empty"),
            HeuristicFeatureSpec("Center Dominance (Tuned)", "10.0", "Discs in central column, maximizing multi-window participation"),
        ),
        default_k=5,
        accent_hex="#e8c26a",
        scene_image="wallpaperflare.com_wallpaper (1).jpg",
        intro_taunt="Your sister played bravely beneath these wings. Let us see if your mind sees deeper than hers.",
        score_taunt="Another window closes. From above, every stone belongs to the Spire.",
        flinch_line="Impossible—that line was meant to be ash!",
        defeat_line="The ash feathers scatter into golden light... your sister's spirit rises free.",
        victory_taunt="Two siblings, one silence. The Spire remains unbroken.",
    ),
)

DEVIL_BY_ID: dict[str, DevilProfile] = {d.devil_id: d for d in DEVILS}
