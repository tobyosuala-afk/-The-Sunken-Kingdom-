#!/usr/bin/env python3
"""
The Sunken Kingdom — A choice-driven command-line adventure.
Single-file OOP design: inheritance, encapsulation, composition, polymorphism.
"""

from __future__ import annotations

import json
import random
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

SAVE_PATH = Path(__file__).with_name("sunken_kingdom_save.json")

# ---------------------------------------------------------------------------
# Narration & UI helpers
# ---------------------------------------------------------------------------


class Narrator:
    """Central voice for story text."""

    @staticmethod
    def say(text: str) -> None:
        print(f"\n{text}\n")

    @staticmethod
    def pause(text: str = "") -> None:
        if text:
            print(text)
        input("Press Enter to continue...")


def clear_line() -> None:
    print("-" * 60)


def menu(prompt: str, options: Sequence[str]) -> int:
    """Numbered menu; returns 1-based index."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        raw = input("> ").strip()
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(options):
                return choice
        print(f"Choose 1–{len(options)}.")


def menu_or_quit(prompt: str, options: Sequence[str]) -> Optional[int]:
    """Menu with optional quit (0)."""
    print(f"\n{prompt}")
    print("  0. Main menu / quit to title")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        raw = input("> ").strip()
        if raw == "0":
            return None
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(options):
                return choice
        print(f"Choose 0–{len(options)}.")


# ---------------------------------------------------------------------------
# Items (Item → Consumable / Equipment / SpecialItem)
# ---------------------------------------------------------------------------


class Item(ABC):
    def __init__(self, name: str, description: str, weight: float = 1.0) -> None:
        self._name = name
        self._description = description
        self._weight = weight

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def weight(self) -> float:
        return self._weight

    @abstractmethod
    def use(self, player: "Player", target: Optional["Character"] = None) -> str:
        pass

    def __str__(self) -> str:
        return self._name


class Consumable(Item):
    """Potions with permanent stat effects."""

    def __init__(
        self,
        name: str,
        description: str,
        hp_bonus: int = 0,
        dmg_bonus: int = 0,
        spd_bonus: int = 0,
        weight: float = 0.5,
    ) -> None:
        super().__init__(name, description, weight)
        self._hp_bonus = hp_bonus
        self._dmg_bonus = dmg_bonus
        self._spd_bonus = spd_bonus

    def use(self, player: "Player", target: Optional["Character"] = None) -> str:
        player.apply_permanent_bonus(self._hp_bonus, self._dmg_bonus, self._spd_bonus)
        return (
            f"You drink the {self._name}. "
            f"(+{self._hp_bonus} HP, +{self._dmg_bonus} DMG, +{self._spd_bonus} SPD — permanent)"
        )


class Equipment(Item):
    """Weapons and armour."""

    def __init__(
        self,
        name: str,
        description: str,
        dmg_bonus: int = 0,
        spd_bonus: int = 0,
        hp_bonus: int = 0,
        is_weapon: bool = True,
        weight: float = 2.0,
    ) -> None:
        super().__init__(name, description, weight)
        self._dmg_bonus = dmg_bonus
        self._spd_bonus = spd_bonus
        self._hp_bonus = hp_bonus
        self._is_weapon = is_weapon

    @property
    def dmg_bonus(self) -> int:
        return self._dmg_bonus

    @property
    def spd_bonus(self) -> int:
        return self._spd_bonus

    @property
    def hp_bonus(self) -> int:
        return self._hp_bonus

    @property
    def is_weapon(self) -> bool:
        return self._is_weapon

    def use(self, player: "Player", target: Optional["Character"] = None) -> str:
        if self._is_weapon:
            return player.equip(self)
        player.apply_permanent_bonus(self._hp_bonus, 0, 0)
        return f"You don the {self._name}. (+{self._hp_bonus} max HP)"


class SpecialItem(Equipment):
    """Legendary gear (Moon, Sun, Sword of Light, Trick Sword, Warm Cloak)."""

    def __init__(
        self,
        name: str,
        description: str,
        dmg_bonus: int = 0,
        spd_bonus: int = 0,
        special_tag: str = "",
        is_weapon: bool = True,
        weight: float = 3.0,
    ) -> None:
        super().__init__(name, description, dmg_bonus, spd_bonus, 0, is_weapon, weight)
        self.special_tag = special_tag  # warm_cloak, trick_sword, moon, sun, light

    def use(self, player: "Player", target: Optional["Character"] = None) -> str:
        if self.special_tag == "warm_cloak":
            return f"You wrap yourself in the {self._name}. The bitter cold will not stop you now."
        return super().use(player, target)


class ThrowableItem(Item):
    """Crystal shards and bombs."""

    def __init__(self, name: str, description: str, enemy_damage: int, self_damage: int = 0) -> None:
        super().__init__(name, description, 1.0)
        self._enemy_damage = enemy_damage
        self._self_damage = self_damage

    def use(self, player: "Player", target: Optional["Character"] = None) -> str:
        msg_parts: List[str] = []
        if self._self_damage:
            player.take_damage(self._self_damage)
            msg_parts.append(f"The blast tears through you for {self._self_damage} damage!")
        if target and self._enemy_damage:
            target.take_damage(self._enemy_damage)
            msg_parts.append(f"{target.name} takes {self._enemy_damage} damage!")
        return " ".join(msg_parts) if msg_parts else "Nothing happens."


# Item factory registry
ITEM_REGISTRY: Dict[str, Callable[[], Item]] = {
    "Wooden Sword": lambda: Equipment("Wooden Sword", "A sturdy training blade.", 1, 20),
    "Basic Armour": lambda: Equipment("Basic Armour", "Worn leather plates.", 0, 0, 2, False),
    "Health Potion": lambda: Consumable("Health Potion", "Restores vitality permanently.", 2, 0, 0),
    "Strength Potion": lambda: Consumable("Strength Potion", "Hardens your strikes.", 0, 2, 0),
    "Haste Potion": lambda: Consumable("Haste Potion", "Quickens your reflexes.", 0, 0, 20),
    "Goblin Bow": lambda: Equipment("Goblin Bow", "Crude but swift.", 2, 50),
    "Bandit Cutlass": lambda: Equipment("Bandit Cutlass", "A curved raider blade.", 4, 30),
    "Giant Battleaxe": lambda: Equipment("Giant Battleaxe", "Heavy royal guard weapon.", 9, 10),
    "Moon Sword": lambda: SpecialItem(
        "Moon Sword", "Pale light ripples along the edge.", 6, 20, "moon"
    ),
    "Sun Sword": lambda: SpecialItem(
        "Sun Sword", "Warmth radiates from the golden hilt.", 6, 20, "sun"
    ),
    "Sword of Light": lambda: SpecialItem(
        "Sword of Light", "Blinding radiance against the dark.", 8, 50, "light"
    ),
    "Trick Sword": lambda: SpecialItem(
        "Trick Sword",
        "It hums with impossible power—and impossible danger.",
        1_000_000,
        1_000_000,
        "trick",
    ),
    "Warm Cloak": lambda: SpecialItem(
        "Warm Cloak", "Enchanted fur that never chills.", 0, 0, "warm_cloak", False
    ),
    "Crystal Shard": lambda: ThrowableItem("Crystal Shard", "Sharp fragment.", 3, 0),
    "Bomb": lambda: ThrowableItem("Bomb", "Unstable powder keg.", 0, 100),
}


def make_item(name: str) -> Item:
    factory = ITEM_REGISTRY.get(name)
    if not factory:
        raise KeyError(name)
    return factory()


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------


class Character:
    def __init__(
        self,
        name: str,
        health: int,
        damage: int,
        speed: int,
        dialogue: Optional[List[str]] = None,
    ) -> None:
        self._name = name
        self._max_health = health
        self._health = health
        self._base_damage = damage
        self._speed = speed
        self._dialogue = dialogue or []

    @property
    def name(self) -> str:
        return self._name

    @property
    def health(self) -> int:
        return self._health

    @property
    def max_health(self) -> int:
        return self._max_health

    @property
    def damage(self) -> int:
        return self._base_damage

    @property
    def speed(self) -> int:
        return self._speed

    @property
    def is_alive(self) -> bool:
        return self._health > 0

    def speak(self) -> None:
        if self._dialogue:
            Narrator.say(f'{self._name}: "{random.choice(self._dialogue)}"')
        else:
            Narrator.say(f"{self._name} has nothing to say.")

    def attack(self, target: "Character") -> int:
        dmg = self.total_damage()
        return target.take_damage(dmg)

    def total_damage(self) -> int:
        return self._base_damage

    def take_damage(self, amount: int) -> int:
        actual = max(0, amount)
        self._health = max(0, self._health - actual)
        return actual

    def heal(self, amount: int) -> None:
        self._health = min(self._max_health, self._health + amount)


class NPC(Character):
    def offer_strength_potions(self, player: "Player") -> None:
        """Mira sells Strength Potions by permanently lowering other stats."""
        Narrator.say(
            f'{self._name} uncorks a vial that smells of iron and ash.\n'
            '"I will sell you Strength Potions, Kael — but the power must be paid for. '
            'I shall draw it from your health, your speed, or your raw might. '
            'Each vial costs a piece of what you are."'
        )
        while True:
            choice = menu(
                "Mira's Strength Potions — sacrifice another stat?",
                [
                    "Buy Strength Potion (−2 max HP)",
                    "Buy Strength Potion (−10 Speed)",
                    "Buy Strength Potion (−1 Damage)",
                    "Leave Mira's stall",
                ],
            )
            if choice == 4:
                Narrator.say('"Wise or timid — either way, choose your path," Mira says.')
                break
            if choice == 1:
                if player.decrease_stat_for_trade(hp=2):
                    pot = make_item("Strength Potion")
                    Narrator.say(
                        "Mira siphons warmth from your chest. "
                        + pot.use(player)
                    )
                else:
                    Narrator.say('"You have no more life to spare," Mira warns.')
            elif choice == 2:
                if player.decrease_stat_for_trade(spd=10):
                    pot = make_item("Strength Potion")
                    Narrator.say(
                        "Your legs grow heavy as Mira bottles your swiftness into strength. "
                        + pot.use(player)
                    )
                else:
                    Narrator.say('"You are already slow as stone," Mira mutters.')
            elif choice == 3:
                if player.decrease_stat_for_trade(dmg=1):
                    pot = make_item("Strength Potion")
                    Narrator.say(
                        "Mira twists your muscle into a denser, crueler power. "
                        + pot.use(player)
                    )
                else:
                    Narrator.say('"I cannot carve strength from nothing," she says.')

    def trade(self, player: "Player") -> None:
        """After the loud approach — additional barter."""
        self.offer_strength_potions(player)


class Enemy(Character):
    def __init__(
        self,
        name: str,
        health: int,
        damage: int,
        speed: int,
        dialogue: Optional[List[str]] = None,
    ) -> None:
        super().__init__(name, health, damage, speed, dialogue)

    def attack(self, target: Character) -> int:
        return super().attack(target)


class Dragon(Enemy):
    """Curse spawn — nearly unstoppable except with Trick Sword."""

    def chant_give_up(self) -> None:
        """Required dialogue whenever the dragon acts during combat."""
        print('The Dragon roars: "give up"')

    def speak(self) -> None:
        self.chant_give_up()

    def attack(self, target: Character) -> int:
        self.chant_give_up()
        return super().attack(target)


class Player(Character):
    BASE_HP = 5
    BASE_DMG = 1
    BASE_SPD = 10
    DEFAULT_WEIGHT = 20.0

    def __init__(self) -> None:
        super().__init__("Kael", self.BASE_HP, self.BASE_DMG, self.BASE_SPD)
        self._bonus_hp = 0
        self._bonus_dmg = 0
        self._bonus_spd = 0
        self.inventory: List[Item] = []
        self.current_location: str = "Forgotten Village"
        self.equipped_weapon: Optional[Equipment] = None
        self.max_carry_weight: float = self.DEFAULT_WEIGHT
        self.flags: Dict[str, bool] = {
            "rowan_curse": False,
            "chose_trick_sword": False,
            "has_warm_cloak": False,
            "library_done": False,
            "outer_world_seen": False,
            "frozen_softlock": False,
        }

    def total_damage(self) -> int:
        weapon_dmg = self.equipped_weapon.dmg_bonus if self.equipped_weapon else 0
        return self._base_damage + self._bonus_dmg + weapon_dmg

    @property
    def speed(self) -> int:
        weapon_spd = self.equipped_weapon.spd_bonus if self.equipped_weapon else 0
        return self._speed + self._bonus_spd + weapon_spd

    @property
    def max_health(self) -> int:
        armour_hp = sum(
            i.hp_bonus for i in self.inventory if isinstance(i, Equipment) and not i.is_weapon
        )
        return self._max_health + self._bonus_hp + armour_hp

    def apply_permanent_bonus(self, hp: int, dmg: int, spd: int) -> None:
        self._bonus_hp += hp
        self._bonus_dmg += dmg
        self._bonus_spd += spd
        self._max_health = max(self.BASE_HP, self._max_health + hp)
        self._health = max(1, min(self.max_health, self._health + hp))

    def decrease_stat_for_trade(self, hp: int = 0, dmg: int = 0, spd: int = 0) -> bool:
        """Reduce stats for Mira's Strength Potion bargains. Returns False if too weak."""
        if hp and self.max_health - hp < self.BASE_HP:
            return False
        if dmg and self._base_damage + self._bonus_dmg - dmg < 1:
            return False
        if spd and self.speed - spd < 1:
            return False
        self.apply_permanent_bonus(-hp, -dmg, -spd)
        return True

    def move(self, place_name: str) -> None:
        self.current_location = place_name

    def pickup(self, item: Item) -> bool:
        weight = sum(i.weight for i in self.inventory) + item.weight
        if weight > self.max_carry_weight:
            Narrator.say("Your pack is too heavy.")
            return False
        self.inventory.append(item)
        if item.name == "Trick Sword":
            self.flags["chose_trick_sword"] = True
        if item.name == "Warm Cloak":
            self.flags["has_warm_cloak"] = True
        return True

    def equip(self, weapon: Equipment) -> str:
        if not weapon.is_weapon:
            return "That is not a weapon."
        self.equipped_weapon = weapon
        return f"You equip the {weapon.name}."

    def use_item(self, item: Item, target: Optional[Character] = None) -> str:
        return item.use(self, target)

    def view_inventory(self) -> None:
        clear_line()
        print("INVENTORY")
        if not self.inventory:
            print("  (empty)")
        for i, item in enumerate(self.inventory, 1):
            eq = " [equipped]" if item is self.equipped_weapon else ""
            print(f"  {i}. {item.name} — {item.description}{eq}")
        print(f"\nCarry: {sum(it.weight for it in self.inventory):.1f}/{self.max_carry_weight}")
        print(
            f"Stats — HP: {self.health}/{self.max_health} | "
            f"DMG: {self.total_damage()} | SPD: {self.speed}"
        )
        clear_line()

    def has_item(self, name: str) -> bool:
        return any(i.name == name for i in self.inventory)

    def remove_item(self, name: str) -> Optional[Item]:
        for item in self.inventory:
            if item.name == name:
                self.inventory.remove(item)
                if self.equipped_weapon is item:
                    self.equipped_weapon = None
                return item
        return None


# ---------------------------------------------------------------------------
# Places (composition of items & characters)
# ---------------------------------------------------------------------------


class Place:
    def __init__(
        self,
        name: str,
        description: str,
        items: Optional[List[str]] = None,
        characters: Optional[List[Character]] = None,
    ) -> None:
        self._name = name
        self._description = description
        self._items = items or []
        self._characters = characters or []

    @property
    def name(self) -> str:
        return self._name

    def describe(self) -> None:
        Narrator.say(self._description)


# ---------------------------------------------------------------------------
# Combat
# ---------------------------------------------------------------------------


def calc_dodge_chance(attacker_spd: int, defender_spd: int) -> float:
    diff = max(0, defender_spd - attacker_spd)
    return min(0.9, diff * 0.10)


class CombatEngine:
    """Turn-based battles with dodge and combat log."""

    def __init__(self, game: "Game") -> None:
        self.game = game

    def run_battle(self, enemies: List[Enemy], intro: str) -> bool:
        player = self.game.player
        Narrator.say(intro)
        living = list(enemies)
        turn = 1
        while player.is_alive and living:
            living = [e for e in living if e.is_alive]
            if not living:
                break
            clear_line()
            print(f"--- COMBAT — Round {turn} ---")
            print(f"Kael: {player.health}/{player.max_health} HP")
            for e in living:
                print(f"  {e.name}: {e.health}/{e.max_health} HP")
            choice = menu(
                "Your action:",
                ["Attack", "Use Item", "View Stats"],
            )
            if choice == 3:
                player.view_inventory()
                continue
            if choice == 2:
                if not self._use_item_in_combat(player, living):
                    continue
            else:
                target = living[0]
                if len(living) > 1:
                    idx = menu("Attack whom?", [e.name for e in living]) - 1
                    target = living[idx]
                if isinstance(target, Dragon):
                    target.chant_give_up()
                self._player_attack(player, target)
            if not player.is_alive:
                break
            self._maybe_spawn_dragon(player, living)
            for enemy in [e for e in living if e.is_alive]:
                if not player.is_alive:
                    break
                if isinstance(enemy, Dragon):
                    enemy.chant_give_up()
                self._enemy_turn(enemy, player)
            turn += 1
        won = player.is_alive and not any(e.is_alive for e in living)
        if won:
            Narrator.say("Victory! The foes fall before Kael.")
        elif not player.is_alive:
            Narrator.say("Kael collapses...")
        return won

    def _player_attack(self, player: Player, target: Enemy) -> None:
        dodge = calc_dodge_chance(player.speed, target.speed)
        if random.random() < dodge:
            print(f"{target.name} dodges Kael's strike! ({dodge*100:.0f}% dodge)")
            return
        dmg = player.total_damage()
        dealt = target.take_damage(dmg)
        print(f"Kael strikes {target.name} for {dealt} damage.")

    def _enemy_turn(self, enemy: Enemy, player: Player) -> None:
        dodge = calc_dodge_chance(enemy.speed, player.speed)
        if random.random() < dodge:
            print(f"Kael dodges! ({dodge*100:.0f}% dodge)")
            return
        dealt = enemy.attack(player)
        print(f"{enemy.name} hits Kael for {dealt} damage.")

    def _maybe_spawn_dragon(self, player: Player, living: List[Enemy]) -> None:
        """1% curse spawn — dragon joins the fight and chants 'give up' each round."""
        if not player.flags.get("rowan_curse"):
            return
        if any(isinstance(e, Dragon) for e in living):
            return
        if random.random() >= 0.01:
            return
        Narrator.say("Elder Rowan's curse manifests — a DRAGON tears through reality!")
        dragon = Dragon("Cursed Dragon", 1000, 1000, 50)
        dragon.chant_give_up()
        living.append(dragon)
        Narrator.say("The beast joins the battle. Its voice rattles your bones: \"give up\"")

    def _use_item_in_combat(self, player: Player, enemies: List[Enemy]) -> bool:
        usable = [
            i
            for i in player.inventory
            if isinstance(i, (Consumable, ThrowableItem))
        ]
        if not usable:
            print("No usable items.")
            return False
        idx = menu("Use which item?", [u.name for u in usable]) - 1
        item = usable[idx]
        target: Optional[Character] = None
        if isinstance(item, ThrowableItem) and item.name == "Crystal Shard":
            living = [e for e in enemies if e.is_alive]
            if living:
                tidx = menu("Throw at?", [e.name for e in living]) - 1
                target = living[tidx]
        msg = player.use_item(item, target)
        print(msg)
        if isinstance(item, (Consumable, ThrowableItem)):
            player.remove_item(item.name)
        return True


# ---------------------------------------------------------------------------
# Trivia (Sunken Library)
# ---------------------------------------------------------------------------

LIBRARY_QUESTIONS: List[Tuple[str, List[str], int]] = [
    ("What element opposes fire?", ["Water", "Stone", "Wind", "Light"], 1),
    ("Capital of the old kingdom?", ["Alden", "Merrow", "Vesper", "Keth"], 2),
    ("Mordren's title before the conquest?", ["Archmage", "Warlord", "King", "Shadow"], 1),
    ("How many days did Mordren take to conquer the world?", ["3", "7", "10", "30"], 2),
    ("The Moon Sword is forged from?", ["Starlight", "Obsidian", "Silver", "Dreams"], 1),
    ("Ancient word for 'sacrifice'?", ["Vael", "Mor", "Keth", "Ren"], 1),
    ("Who wrote the diary Kael found?", ["Rowan", "Mira", "Mordren", "The Prince"], 3),
    ("Sun Sword's true name in Old Tongue?", ["Solbrand", "Helios", "Auravel", "Dawnbreak"], 3),
]

SUN_SWORD_QUESTION = (
    "To bind sun and moon, speak the vow of the First Flame. Finish: 'By light I —'",
    ["End", "Burn", "Serve", "Fall"],
    2,
)


# ---------------------------------------------------------------------------
# Game state & locations
# ---------------------------------------------------------------------------


LOCATION_ORDER = [
    "Forgotten Village",
    "Whispering Forest",
    "Old Watchtower",
    "Crystal Cave",
    "Bandit Camp",
    "Abandoned Mine",
    "Sunken Library",
    "Frozen Pass",
    "Royal Gardens",
    "Sunken Castle",
]


class Game:
    """Main game controller — scenes, progression, save/load."""

    def __init__(self) -> None:
        self.player = Player()
        self.combat = CombatEngine(self)
        self.location_index = 0
        self.game_over = False
        self.ending: Optional[str] = None

    def days_remaining(self) -> int:
        return max(1, 10 - self.location_index)

    def show_day_banner(self) -> None:
        print(f"\n{'='*60}")
        print(f"DAYS UNTIL THE END OF THE WORLD: {self.days_remaining()}")
        print(f"{'='*60}")

    def run(self) -> None:
        while not self.game_over and self.location_index < len(LOCATION_ORDER):
            handlers = [
                self._scene_forgotten_village,
                self._scene_whispering_forest,
                self._scene_old_watchtower,
                self._scene_crystal_cave,
                self._scene_bandit_camp,
                self._scene_abandoned_mine,
                self._scene_sunken_library,
                self._scene_frozen_pass,
                self._scene_royal_gardens,
                self._scene_sunken_castle,
            ]
            handlers[self.location_index]()
            if self.game_over:
                return
            if self.location_index < len(LOCATION_ORDER) - 1:
                hub = menu(
                    "Camp for a moment?",
                    ["Continue toward the next day", "View inventory", "Save game"],
                )
                if hub == 2:
                    self.player.view_inventory()
                elif hub == 3:
                    self.save_game()
            self.location_index += 1

    def _title_screen(self) -> None:
        print(
            r"""
   _____ _             _         _    _           _     _
  / ____| |           | |       | |  | |         | |   | |
 | (___ | |_ _   _  __| | ___   | |  | |___  __ _| | __| |
  \___ \| __| | | |/ _` |/ _ \  | |  | / __|/ _` | |/ _` |
  ____) | |_| |_| | (_| |  __/  | |__| \__ \ (_| | | (_| |
 |_____/ \__|\__,_|\__,_|\___|   \____/|___/\__,_|_|\__,_|
              T H E   S U N K E N   K I N G D O M
                        by Toby Osuala
"""
        )
        choice = menu(
            "Welcome, traveler.",
            ["New Game", "Load Game", "Quit"],
        )
        if choice == 3:
            sys.exit(0)
        if choice == 2:
            if not self.load_game():
                Narrator.say("No save found. Starting anew.")
                self._intro()
            return
        self._intro()

    def play(self) -> None:
        """Title screen then main story loop."""
        self._title_screen()
        self.run()

    def _intro(self) -> None:
        entered = input("\nThe narrator asks: What is your name? ").strip() or "Traveler"
        Narrator.say(
            f'You whisper "{entered}", but the diary already knows you.\n'
            "The name burned into fate is Kael."
        )
        Narrator.say(
            "You awaken in the Forgotten Village clutching Mordren's diary.\n"
            "He conquered the world in one week. In ten days he will destroy it.\n"
            "A black-sealed letter waits on the floor beside you — you will read it soon."
        )
        Narrator.pause()

    def _advance(self, place_name: str, description: str) -> None:
        self.player.move(place_name)
        self.show_day_banner()
        Place(place_name, description).describe()

    # --- Scene handlers ---

    def _scene_forgotten_village(self) -> None:
        self._advance(
            "Forgotten Village",
            "Fog clings to broken homes. A wooden rack holds a sword; "
            "armour hangs beside it.",
        )
        Narrator.say(
            "You unfold the letter from Mordren. The ink seems still wet:\n\n"
            '    "Kael,\n\n'
            "    I came to this world because of you. In ten days, meet me in my Castle "
            "at the heart of the Sunken Kingdom — or I will destroy the world and "
            "everything in it.\n\n"
            "    Do not keep me waiting.\n\n"
            '    — Mordren"\n'
        )
        Narrator.say(
            "The diary in your pack confirms the same threat: one week to conquer, "
            "ten days until the end. The letter and the diary both demand an answer."
        )
        Narrator.pause("You steady your breath and search for gear.")
        choice = menu("Choose your starting gear:", ["Take Wooden Sword", "Take Basic Armour"])
        if choice == 1:
            item = make_item("Wooden Sword")
            self.player.pickup(item)
            self.player.equip(item)  # type: ignore[arg-type]
        else:
            armour = make_item("Basic Armour")
            self.player.pickup(armour)
            armour.use(self.player)
        Narrator.pause("You step toward the Whispering Forest.")

    def _scene_whispering_forest(self) -> None:
        self._advance(
            "Whispering Forest",
            "Trees murmur Mordren's name. Slimes ooze from the undergrowth.",
        )
        Narrator.say("Before the battle, the canopy darkens.")
        if not self.combat.run_battle(
            [Enemy("Slime", 4, 1, 5), Enemy("Slime", 4, 1, 5)],
            "Two slimes block the path!",
        ):
            self._handle_death()
            return
        Narrator.say("Among the roots you find abandoned supplies.")
        self.player.pickup(make_item("Health Potion"))
        self.player.pickup(make_item("Strength Potion"))
        Narrator.pause()

    def _scene_old_watchtower(self) -> None:
        self._advance(
            "Old Watchtower",
            "A crumbling watchtower overlooks the valley. Goblins have claimed it.",
        )
        Narrator.say("Steel clashes on the stairs.")
        enemies = [
            Enemy("Goblin", 6, 2, 8),
            Enemy("Goblin", 6, 2, 8),
            Enemy("Red Goblin", 10, 3, 12),
        ]
        if not self.combat.run_battle(enemies, "Goblins swarm Kael!"):
            self._handle_death()
            return
        rowan = NPC(
            "Elder Rowan",
            20,
            0,
            5,
            [
                "Mordren was not always a monster.",
                "Perhaps there is a faster way to end him.",
            ],
        )
        Narrator.say(
            "Elder Rowan descends, trembling. He speaks of Mordren's rise — "
            "a scholar who touched forbidden power."
        )
        rowan.speak()
        choice = menu(
            "How do you respond?",
            [
                "Tell Rowan that Mordren appeared only because of you",
                "Stay silent and listen",
            ],
        )
        if choice == 1:
            Narrator.say(
                'Kael meets Rowan\'s gaze. "Mordren appeared only because of me, Elder."'
            )
            Narrator.say(
                'Rowan flinches as if struck. His voice drops to a whisper.\n'
                '"Kael... are you telling the truth?"'
            )
            truth_choice = menu(
                "Rowan waits for your answer:",
                ["Yes — I am telling the truth", "No — I spoke in anger and regret it"],
            )
            if truth_choice == 1:
                Narrator.say(
                    'Rowan\'s eyes blaze. "Then share his curse!" he screams.\n'
                    "A hex settles on your soul. (Bad Ending 4 — Dragon curse active)"
                )
                self.player.flags["rowan_curse"] = True
            else:
                Narrator.say(
                    'Rowan exhales shakily. "See that your tongue does not doom us both."\n'
                    "He turns away, but the air still feels wrong."
                )
        else:
            Narrator.say(
                "Rowan nods slowly. 'Seek the fast blade, or the fast path — "
                "but do not trust every glittering sword.'"
            )
        if not self.player.has_item("Goblin Bow"):
            if menu("Search the tower?", ["Yes", "No"]) == 1:
                self.player.pickup(make_item("Goblin Bow"))
                Narrator.say("You claim a Goblin Bow from a fallen archer.")
        Narrator.pause()

    def _scene_crystal_cave(self) -> None:
        self._advance(
            "Crystal Cave",
            "Crystals pulse with sickly light. Trolls guard the deep veins.",
        )
        if not self.combat.run_battle(
            [Enemy("Troll", 14, 4, 6), Enemy("Troll", 14, 4, 6)],
            "Trolls roar and charge!",
        ):
            self._handle_death()
            return
        self.player.pickup(make_item("Crystal Shard"))
        self.player.pickup(make_item("Bomb"))
        Narrator.say("You pocket crystal shards and a volatile bomb.")
        Narrator.pause()

    def _scene_bandit_camp(self) -> None:
        self._advance(
            "Bandit Camp",
            "Smoke rises from Bandit Camp. Mira, the magical merchant, "
            "offers counsel before you enter.",
        )
        mira = NPC("Mira", 1, 0, 1, ["Loud or quiet — choose wisely."])
        Narrator.say(
            "The Magical Merchant Mira steps from behind a wagon, eyes glittering.\n"
            '"Listen well, Kael. There are two ways past this camp.\n'
            "A loud approach — storm the tents, cut through every bandit, and earn "
            "my trade when the smoke clears.\n"
            "Or a quiet approach — slip through the shadows to the Prince of Thieves "
            "and whatever blade he guards.\n"
            'Choose your road — but choose before the sun sets."'
        )
        mira.speak()
        if menu("Speak with Mira about her Strength Potions?", ["Yes", "No"]) == 1:
            mira.offer_strength_potions(self.player)
        approach = menu("How do you enter the camp?", ["Loud approach", "Quiet approach"])
        if approach == 1:
            bandits = [Enemy(f"Bandit", 7, 2, 10) for _ in range(5)]
            if not self.combat.run_battle(bandits, "Bandits rush from every tent!"):
                self._handle_death()
                return
            Narrator.say("Mira appears from the smoke, grinning.")
            mira.trade(self.player)
            if menu("Take a Bandit Cutlass from the loot?", ["Yes", "No"]) == 1:
                blade = make_item("Bandit Cutlass")
                self.player.pickup(blade)
        else:
            Narrator.say(
                "You slip through shadows until the Prince of Thieves blocks your way."
            )
            Narrator.say(
                'The Prince of Thieves rests a hand on his scabbard and smirks.\n'
                '"Before we cross blades, Kael — tell me honestly... do you like my sword?"'
            )
            sword_opinion = menu(
                "The Prince of Thieves awaits your answer:",
                [
                    "Yes — it's a magnificent blade",
                    "No — I've seen finer steel",
                    "I like it enough to take it from you",
                ],
            )
            if sword_opinion == 1:
                Narrator.say(
                    '"Flattery won\'t save you," the Prince laughs, "but good taste might."'
                )
            elif sword_opinion == 2:
                Narrator.say(
                    '"Then you\'ll bleed on inferior steel," the Prince snarls, drawing his weapon.'
                )
            else:
                Narrator.say(
                    '"Bold," the Prince whispers. "Let us see if your hands are as greedy as your tongue."'
                )
            prince = Enemy("Prince of Thieves", 15, 5, 14)
            if not self.combat.run_battle(
                [prince],
                "The Prince twirls his dagger. 'Your life or your gold?'",
            ):
                choice = menu(
                    "You fell to the Prince...",
                    ["Accept defeat (intentional loss)", "Restart from last save"],
                )
                if choice == 1:
                    self._bad_ending_2()
                else:
                    self._handle_death()
                return
            moon = make_item("Moon Sword")
            self.player.pickup(moon)
            Narrator.say("You claim the Moon Sword from the Prince's vault.")
            cont = menu(
                "The Moon Sword hums with destiny.",
                ["Continue the journey", "Intentionally fall in battle (Moon path)"],
            )
            if cont == 2:
                self._bad_ending_2()
                return
        Narrator.pause()

    def _scene_abandoned_mine(self) -> None:
        self._advance(
            "Abandoned Mine",
            "The Abandoned Mine yawns. A single chest waits — two relics, one choice.",
        )
        choice = menu(
            "You may take ONLY ONE:",
            ["Warm Cloak - For freezing weather", "Trick Sword - For overwhelming power"],
        )
        if choice == 1:
            self.player.pickup(make_item("Warm Cloak"))
            Narrator.say("You take the Warm Cloak. Warmth spreads through your bones.")
        else:
            trick = make_item("Trick Sword")
            self.player.pickup(trick)
            self.player.equip(trick)  # type: ignore[arg-type]
            Narrator.say(
                "The Trick Sword sears your hands. Power floods Kael — "
                "and a dread premonition."
            )
        Narrator.pause()

    def _scene_sunken_library(self) -> None:
        self._advance(
            "Sunken Library",
            "Flooded shelves rise from black water. Runes demand answers.",
        )
        correct_count = 0
        q_index = 0
        while q_index < len(LIBRARY_QUESTIONS):
            q, opts, ans = LIBRARY_QUESTIONS[q_index]
            Narrator.say(f"Question {q_index + 1}: {q}")
            pick = menu("Answer:", opts)
            if pick == ans:
                correct_count += 1
                Narrator.say("Correct! The runes glow.")
                if correct_count % 2 == 0:
                    Narrator.say("A Warlock materializes from the ink!")
                    if not self.combat.run_battle(
                        [Enemy("Warlock", 12, 5, 15)],
                        "The Warlock strikes!",
                    ):
                        self._handle_death()
                        return
            else:
                Narrator.say("Wrong. The water rises, but the path remains.")
            q_index += 1
        self.player.flags["library_done"] = True
        if menu("Attempt the final Sun Sword riddle?", ["Yes", "No"]) == 1:
            q, opts, ans = SUN_SWORD_QUESTION
            Narrator.say(q)
            if menu("Answer:", opts) == ans:
                self.player.pickup(make_item("Sun Sword"))
                Narrator.say("The Sun Sword manifests in a burst of flame!")
            else:
                Narrator.say("The flame sputters out. You may continue without it.")
        if self.player.has_item("Moon Sword") and self.player.has_item("Sun Sword"):
            Narrator.say(
                "With Moon and Sun united, a hidden archway opens — the Outer World."
            )
            self._scene_outer_world()
        Narrator.pause()

    def _scene_outer_world(self) -> None:
        if not (self.player.has_item("Moon Sword") and self.player.has_item("Sun Sword")):
            return
        self.player.flags["outer_world_seen"] = True
        Narrator.say(
            "Beyond reality, the Outer World floats — threads tying Mordren to "
            "existence stretch like spider silk."
        )
        choice = menu(
            "The narrator speaks: Kael may sever those threads, but only by "
            "sacrificing himself. Both will die; the world will live.",
            [
                "Accept — sacrifice yourself (Secret Good Ending)",
                "Refuse — try to fight the connection alone",
            ],
        )
        if choice == 1:
            self._victory_good_2()
        else:
            self._bad_ending_2()

    def _scene_frozen_pass(self) -> None:
        self._advance(
            "Frozen Pass",
            "Wind howls across the Frozen Pass. Ice swallows sound.",
        )
        Narrator.say("A hooded figure materialises from the blizzard — ???.")
        Narrator.say(
            '???: "Halt, Kael. Before you take another step — tell me... '
            'do you have a Warm Cloak?"'
        )
        cloak_answer = menu(
            "??? listens for your reply:",
            ["Yes — I have a Warm Cloak", "No — I do not have one"],
        )
        if cloak_answer == 1 and not self.player.flags["has_warm_cloak"]:
            Narrator.say('???: "You lie. The wind knows an uncloaked soul. Mordren has deceived you."')
        elif cloak_answer == 2 and self.player.flags["has_warm_cloak"]:
            Narrator.say('???: "You deny what I can see upon your shoulders. Strange child."')
        elif cloak_answer == 1 and self.player.flags["has_warm_cloak"]:
            Narrator.say(
                '???: "I see its enchantment. Good. Perhaps you will not freeze today."'
            )
        else:
            Narrator.say('???: "Honesty. Cold honesty. The pass will judge you. Mordren has deceived you."')

        if self.player.flags["chose_trick_sword"] and not self.player.flags["has_warm_cloak"]:
            Narrator.say(
                '???: "You chose glittering steel over warmth. The ice remembers. Mordren has deceived you."'
            )
            self._bad_ending_3()
            return
        if not self.player.flags["has_warm_cloak"]:
            Narrator.say(
                "Without the Warm Cloak, the cold gnaws to the bone. "
                "You cannot press onward."
            )
            Narrator.say("Turn back to the mine — you need the Warm Cloak.")
            self.location_index -= 1
            return
        Narrator.say("The Warm Cloak repels the blizzard. ??? steps aside.")
        Narrator.say('???: "Walk on, then... if you dare."')
        Narrator.pause("The path clears toward the Royal Gardens.")

    def _scene_royal_gardens(self) -> None:
        self._advance(
            "Royal Gardens",
            "Overgrown royalty. Giants patrol where kings once strolled.",
        )
        if not self.combat.run_battle(
            [Enemy("Giant", 22, 6, 8), Enemy("Giant", 22, 6, 8)],
            "Giants — the strongest foes yet — lumber forward!",
        ):
            self._handle_death()
            return
        if menu("Explore the Hidden Grove?", ["Enter the grove", "Continue to the castle"]) == 1:
            Narrator.say(
                "Sunlight pierces the grove. A Sword of Light rests in stone."
            )
            blade = make_item("Sword of Light")
            self.player.pickup(blade)
            if menu("Equip Sword of Light now?", ["Yes", "No"]) == 1:
                self.player.equip(blade)  # type: ignore[arg-type]
        if menu("Take a Giant Battleaxe from the battlefield?", ["Yes", "No"]) == 1:
            self.player.pickup(make_item("Giant Battleaxe"))
        Narrator.pause()

    def _scene_sunken_castle(self) -> None:
        self._advance(
            "Sunken Castle",
            "The Sunken Castle rises from the depths. At its heart waits Mordren.",
        )
        Narrator.say(
            "Before the final battle, the diary trembles. This is the last day."
        )
        mordren = Enemy("Mordren", 75, 10, 18)
        Narrator.say(
            "Mordren rises from his throne, the diary's prophecy humming in your bones."
        )
        Narrator.say(
            'Mordren circles you slowly. "Before we end everything, Kael... '
            'are you feeling nervous?"'
        )
        nerves = menu(
            "How do you answer Mordren?",
            [
                "Yes — my hands won't stop shaking",
                "No — I'm ready to end this",
                "Nervous? You should be.",
            ],
        )
        if nerves == 1:
            Narrator.say(
                '"Good," Mordren purrs. "Fear is the last flavour the world will taste."'
            )
        elif nerves == 2:
            Narrator.say(
                '"Brave words," Mordren says. "Let us see if your blade agrees."'
            )
        else:
            Narrator.say(
                'Mordren\'s smile widens. "Spirit. Shame I must crush it."'
            )
        if self.player.has_item("Sword of Light"):
            Narrator.say("The Sword of Light blazes — Mordren recoils! His guard weakens.")
            mordren.take_damage(25)
        if not self.combat.run_battle(
            [mordren],
            "Mordren smiles. 'Kael. You came to die with the world.'",
        ):
            self._bad_ending_1()
            return
        if self.player.flags["chose_trick_sword"]:
            Narrator.say(
                "The Trick Sword shatters the world even as Mordren falls. "
                "This hollow triumph is not the true Good Ending."
            )
            self._offer_restart()
            return
        self._victory_good_1()

    # --- Endings ---

    def _show_game_over(self, title: str) -> None:
        print("\n" + "=" * 60)
        print(f"*** {title} ***")
        print("=" * 60)

    def _victory_good_1(self) -> None:
        self.game_over = True
        self.ending = "good_1"
        self._show_game_over("VICTORY — GOOD ENDING 1")
        Narrator.say(
            "Mordren falls. The tides recede. Kael stands in the ruined hall "
            "as dawn breaks over a world given one more chance."
        )

    def _victory_good_2(self) -> None:
        self.game_over = True
        self.ending = "good_2"
        self._show_game_over("VICTORY — SECRET GOOD ENDING 2")
        Narrator.say(
            "Kael drives Moon and Sun through the weave of reality. He perishes; "
            "Mordren ceases to be. Nations will never know the name of their savior."
        )

    def _bad_ending_1(self) -> None:
        self.game_over = True
        self._show_game_over("GAME OVER — BAD ENDING 1")
        Narrator.say(
            "Mordren stands over Kael's body. With a gesture, the sky tears open. "
            "Fire and salt consume every kingdom. Nothing remains."
        )
        self._offer_restart()

    def _bad_ending_2(self) -> None:
        self.game_over = True
        self._show_game_over("GAME OVER — BAD ENDING 2")
        Narrator.say(
            "The Moon Sword shatters the moment of your defeat. Time rewinds — "
            "you will wake again, but the memory of failure lingers."
        )
        self._offer_restart()

    def _bad_ending_3(self) -> None:
        self.game_over = True
        self.player.flags["frozen_softlock"] = True
        self._show_game_over("GAME OVER — BAD ENDING 3 (SOFTLOCK)")
        Narrator.say(
            "Without the Warm Cloak, the Trick Sword's power means nothing. "
            "Ice entombs Kael. The narrator's voice echoes from far away."
        )
        while True:
            choice = menu(
                '???: "Frozen again. What now?"',
                [
                    "Freeze to death (continue loop)",
                    "Restart the game",
                ],
            )
            if choice == 2:
                self._offer_restart()
                return
            Narrator.say("You freeze. Darkness. ...You awaken, still trapped in ice.")

    def _handle_death(self) -> None:
        if self.player.has_item("Moon Sword") and self.location_index >= 4:
            self._bad_ending_2()
        else:
            Narrator.say("Kael has fallen.")
            self._offer_restart()

    def _offer_restart(self) -> None:
        if menu("Play again?", ["Restart", "Quit"]) == 1:
            self.__init__()
            self.run()
        else:
            sys.exit(0)

    # --- Save / Load ---

    def save_game(self) -> None:
        data = {
            "location_index": self.location_index,
            "player": {
                "health": self.player.health,
                "max_health_base": self.player._max_health,
                "bonus_hp": self.player._bonus_hp,
                "bonus_dmg": self.player._bonus_dmg,
                "bonus_spd": self.player._bonus_spd,
                "inventory": [i.name for i in self.player.inventory],
                "equipped": self.player.equipped_weapon.name
                if self.player.equipped_weapon
                else None,
                "max_carry_weight": self.player.max_carry_weight,
                "flags": self.player.flags,
                "location": self.player.current_location,
            },
        }
        SAVE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        Narrator.say(f"Game saved to {SAVE_PATH.name}.")

    def load_game(self) -> bool:
        if not SAVE_PATH.exists():
            return False
        data = json.loads(SAVE_PATH.read_text(encoding="utf-8"))
        self.location_index = data["location_index"]
        p = data["player"]
        self.player = Player()
        self.player._health = p["health"]
        self.player._max_health = p["max_health_base"]
        self.player._bonus_hp = p["bonus_hp"]
        self.player._bonus_dmg = p["bonus_dmg"]
        self.player._bonus_spd = p["bonus_spd"]
        self.player.max_carry_weight = p["max_carry_weight"]
        self.player.flags = p["flags"]
        self.player.current_location = p["location"]
        for name in p["inventory"]:
            item = make_item(name)
            self.player.inventory.append(item)
        if p["equipped"]:
            for item in self.player.inventory:
                if item.name == p["equipped"] and isinstance(item, Equipment):
                    self.player.equip(item)
                    break
        Narrator.say("Save loaded.")
        return True


def main() -> None:
    try:
        while True:
            game = Game()
            game.play()
            if menu("Return to title?", ["Play again", "Quit"]) != 1:
                break
    except KeyboardInterrupt:
        print("\nFarewell, Kael.")


if __name__ == "__main__":
    main()
