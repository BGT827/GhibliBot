import os
import aiohttp
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import RPCError, FloodWait
from io import BytesIO
from PIL import Image

# Bot configuration
API_ID = "YOUR_API_ID"  # Replace with your api_id
API_HASH = "YOUR_API_HASH"  # Replace with your api_hash
BOT_TOKEN = "YOUR_BOT_TOKEN"  # Replace with your bot token
FOTOR_API_URL = "https://api.fotor.com/v1/ai-tools/studio-ghibli-filter"  # Real Fotor API
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max file size

# Initialize Pyrogram client
app = Client(
    "ghibli_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

async def validate_image(file_path: str, file_size: int) -> bool:
    """Validate image file based on extension and size."""
    if file_size > MAX_FILE_SIZE:
        return False
    extension = os.path.splitext(file_path)[1].lower()
    return extension in ALLOWED_EXTENSIONS

async def apply_ghibli_effect(image_data: bytes) -> bytes:
    """Call Fotor's Studio Ghibli Filter API and return processed image."""
    async with aiohttp.ClientSession() as session:
        form_data = aiohttp.FormData()
        form_data.add_field(
            "image",
            image_data,
            filename="input.jpg",
            content_type="image/jpeg"
        )
        try:
            async with session.post(FOTOR_API_URL, data=form_data) as response:
                if response.status != 200:
                    raise Exception(f"API error: {response.status} - {await response.text()}")
                return await response.read()
        except Exception as e:
            raise Exception(f"Failed to process image: {str(e)}")

async def optimize_image(image_data: bytes) -> bytes:
    """Optimize image for Telegram upload (resize if needed)."""
    img = Image.open(BytesIO(image_data))
    if img.size[0] > 1280 or img.size[1] > 1280:
        img.thumbnail((1280, 1280), Image.LANCZOS)
    output = BytesIO()
    img.convert("RGB").save(output, format="JPEG", quality=85)
    return output.getvalue()

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Handle /start command."""
    await message.reply_text(
        "Welcome to the Ghibli Photo Bot! 🎨\n"
        "Send me a photo, and I'll convert it into a Studio Ghibli-style image!"
    )

@app.on_message(filters.photo & filters.private)
async def handle_photo(client: Client, message: Message):
    """Handle incoming photos and process them."""
    try:
        # Send processing message
        status_msg = await message.reply_text("Processing your photo... ⏳")

        # Get the highest resolution photo
        photo = message.photo[-1]
        file_id = photo.file_id
        file_size = photo.file_size

        # Validate file size and extension
        if not await validate_image(f"temp_{file_id}.jpg", file_size):
            await status_msg.edit_text(
                "Invalid file! Please send a JPG or PNG image under 10MB."
            )
            return

        # Download the photo
        file_path = await client.download_media(
            message=message,
            file_name=f"temp_{file_id}.jpg",
            in_memory=True
        )

        # Read image data
        image_data = file_path.getvalue()

        # Apply Ghibli effect
        try:
            processed_image = await apply_ghibli_effect(image_data)
        except Exception as e:
            await status_msg.edit_text(f"Error processing image: {str(e)}")
            return

        # Optimize processed image
        optimized_image = await optimize_image(processed_image)

        # Send the processed image
        await message.reply_photo(
            photo=BytesIO(optimized_image),
            caption="Here's your Ghibli-style photo! ✨"
        )

        # Update status
        await status_msg.edit_text("Done! Enjoy your Ghibli-style image! 🎉")

    except FloodWait as fw:
        await asyncio.sleep(fw.value)
        await handle_photo(client, message)
    except RPCError as e:
        await status_msg.edit_text(f"Telegram error: {str(e)}")
    except Exception as e:
        await status_msg.edit_text(f"An error occurred: {str(e)}")
    finally:
        # Clean up
        if 'file_path' in locals():
            file_path.close()

async def main():
    """Start the bot."""
    try:
        await app.start()
        print("Bot is running...")
        await app.idle()
    except Exception as e:
        print(f"Failed to start bot: {str(e)}")
    finally:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
