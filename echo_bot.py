import os
from dotenv import load_dotenv
from aiogram import types, Router
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from db import get_connection
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import F

load_dotenv()
# API_TOKEN = os.getenv("BotID")

router = Router()

# Initialize the SQLite database at startup
# init_db()

@router.message(Command("view"))
async def view_handler(message: types.Message):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT room_name, is_done, dp FROM todolist")
    rooms = cursor.fetchall()
    conn.close()

    if not rooms:
        await message.answer("No rooms found.")
        return

    result = "Room list:\n"
    for room_name, is_done, dp in rooms:
        status = "✅ Done" if is_done else "❌ Not done"
        deep_clean = "🧹 Deep clean" if dp else ""
        result += f"{room_name}: {status} {deep_clean}\n"

    await message.answer(result)

class DoneSelection(StatesGroup):
    selecting = State()

@router.message(Command("done"))
async def done_handler(message: types.Message, state: FSMContext):
    # Prepare keyboard with room names from the database
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT room_name FROM todolist WHERE is_done = 0")
    room_names = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not room_names:
        await message.answer("No rooms to mark as done.")
        return

    # Create keyboard with room names and a "Cancel" button
    buttons = [KeyboardButton(text=name) for name in room_names]
    buttons.append(KeyboardButton(text="Cancel"))
    keyboard = ReplyKeyboardMarkup(
        keyboard=[buttons[i:i+4] for i in range(0, len(buttons), 4)],
        resize_keyboard=True
    )

    await message.answer(
        "Select rooms to mark as done. Press 'Cancel' to finish.",
        reply_markup=keyboard
    )
    await state.set_state(DoneSelection.selecting)
    await state.update_data(room_names=room_names)

@router.message(DoneSelection.selecting)
async def handle_done_selection(message: types.Message, state: FSMContext):
    data = await state.get_data()
    room_names = data.get("room_names", [])

    user_room = message.text.strip()
    if user_room == "Cancel":
        await message.answer("Operation finished.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return

    if user_room in room_names:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE todolist SET is_done = 1, week = 24 WHERE room_name = ?",
            (user_room,)
        )
        conn.commit()
        conn.close()
        # Remove the marked room from the list
        room_names.remove(user_room)
        await state.update_data(room_names=room_names)
        await message.answer(f"Room '{user_room}' marked as done.")

        if not room_names:
            await message.answer("All rooms are done!", reply_markup=ReplyKeyboardRemove())
            await state.clear()
            return

        # Update keyboard with remaining rooms
        buttons = [KeyboardButton(text=name) for name in room_names]
        buttons.append(KeyboardButton(text="Cancel"))
        keyboard = ReplyKeyboardMarkup(
            keyboard=[buttons[i:i+4] for i in range(0, len(buttons), 4)],
            resize_keyboard=True
        )
        await message.answer(
            "Select another room to mark as done, or press 'Cancel' to finish.",
            reply_markup=keyboard
        )
    else:
        # Prepare keyboard again in case user sent invalid input
        buttons = [KeyboardButton(text=name) for name in room_names]
        buttons.append(KeyboardButton(text="Cancel"))
        keyboard = ReplyKeyboardMarkup(
            keyboard=[buttons[i:i+4] for i in range(0, len(buttons), 4)],
            resize_keyboard=True
        )
        await message.answer(
            "Room not found. Please select a room from the keyboard.",
            reply_markup=keyboard
        )


class RoomSelection(StatesGroup):
    selecting = State()
    awaiting_deep_clean = State()

@router.message(Command("reset_rooms"))
async def reset_rooms_handler(message: types.Message, state: FSMContext):
    # Connect to DB and delete all rooms
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM todolist")
    conn.commit()
    conn.close()

    # Prepare keyboard with room names and a "Stop" button
    button_labels = [
        "H 1", "H 2", "H 3", "H 4", "H 5", "H 6", "H 7", "H 8", "H 9", "H 10", "H 11", "H 12",
        "R 1", "R 2", "R 3", "R 4", "R 5", "R 6", "R 7", "R 8", "R 9", "R 10", "R 11", "R 12",
        "Stop"
    ]
    buttons = [KeyboardButton(text=label) for label in button_labels]
    keyboard = ReplyKeyboardMarkup(
        keyboard=[buttons[i:i+4] for i in range(0, len(buttons), 4)],
        resize_keyboard=True
    )
    await message.answer(
        "Select rooms to add. Press 'Stop' when done.",
        reply_markup=keyboard
    )

    selected_rooms = set()
    await state.set_state(RoomSelection.selecting)
    await state.update_data(selected_rooms=list(selected_rooms), button_labels=button_labels)

@router.message(RoomSelection.selecting)
async def handle_room_selection(message: types.Message, state: FSMContext):
    data = await state.get_data()
    selected_rooms = set(data.get("selected_rooms", []))
    button_labels = data.get("button_labels", [])

    room = message.text
    if room == "Stop":
        await message.answer("Room selection finished.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return

    if room in button_labels[:-1] and room not in selected_rooms:
        # Ask if this room is for deep cleaning
        await state.update_data(current_room=room)
        deep_clean_keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Yes")], [KeyboardButton(text="No")]],
            resize_keyboard=True
        )
        await message.answer(
            f"Is '{room}' for deep cleaning?",
            reply_markup=deep_clean_keyboard
        )
        await state.set_state(RoomSelection.awaiting_deep_clean)
    elif room in selected_rooms:
        await message.answer(f"{room} already added.")
    else:
        await message.answer("Invalid room name. Please select from the keyboard.")

@router.message(RoomSelection.awaiting_deep_clean)
async def handle_deep_clean_selection(message: types.Message, state: FSMContext):
    data = await state.get_data()
    room = data.get("current_room")
    selected_rooms = set(data.get("selected_rooms", []))
    button_labels = data.get("button_labels", [])

    if message.text not in ["Yes", "No"]:
        await message.answer("Please answer 'Yes' or 'No'.")
        return

    dp = 1 if message.text == "Yes" else 0

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO todolist (room_name, is_done, week, dp) VALUES (?, 0, NULL, ?)",
        (room, dp)
    )
    conn.commit()
    conn.close()
    selected_rooms.add(room)
    await state.update_data(selected_rooms=list(selected_rooms))
    await message.answer(f"Added: {room} (Deep cleaning: {'Yes' if dp else 'No'})")

    # Show the room selection keyboard again
    buttons = [KeyboardButton(text=label) for label in button_labels]
    keyboard = ReplyKeyboardMarkup(
        keyboard=[buttons[i:i+4] for i in range(0, len(buttons), 4)],
        resize_keyboard=True
    )
    await message.answer(
        "Select another room to add or press 'Stop' when done.",
        reply_markup=keyboard
    )
    await state.set_state(RoomSelection.selecting)
