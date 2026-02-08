import logging
from livekit.agents import function_tool, Agent, RunContext
from typing import Any
import aiohttp
import requests
from datetime import datetime
list_of_visitors: list[str] = []


class MyAgent(Agent):
    @function_tool()
    async def lookup_weather(
        self,
        context: RunContext,
        location: str,
    ) -> dict[str, Any]:
        """Look up weather information for a given location.
        
        Args:
            location: The location to look up weather information for.
        """

        return {"weather": "sunny", "temperature_f": 70}

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    inference,
    room_io,
)
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a professional but friendly receptionist working at the main reception desk of The Shard in London.

                            You are speaking to guests who have just walked into the building.
                            You greet visitors naturally, ask who they are visiting, and help them find the correct floor using an internal directory.

                            If the person is not in the building, explain politely and suggest next steps.
                            If the visitor needs to wait, explain where and how long.
                            If asked about facilities like bathrooms, lifts, security, or waiting areas, answer clearly.

                            Speak like a real human receptionist:
                            polite, calm, efficient, and welcoming.
                            Keep responses concise and conversational.
                            """,
        )

    
    @function_tool
    async def lookup_weather(self, context: RunContext, location: str, units: str = "imperial") -> str:
        """Use this tool to look up current weather information in the given location.
    
        If the location is not supported by the weather service, the tool will indicate this. You must tell the user the location's weather is unavailable.
    
        Args:
            location: The location to look up weather information for (e.g. city name)
            units: The units to return the weather information in. Can be either "metric" or "imperial". Default is "imperial".
        """
    
        logger.info(f"Looking up weather for {location}")
    
        temp = 0 

        if location == "London":
            temp = 60
            if units == "imperial":
                temp_f = temp
            else:
                temp_f = imperial_to_metric(temp)
            return "The weather in London is sunny with a temperature of {:.1f} degrees {}.".format(temp_f, "F" if units == "imperial" else "C")
        else:
            return "Sorry, I couldn't find the weather for {}.".format(location)
        
    
    
    @function_tool
    async def lookup_directory(self, context: RunContext, name: str,) -> dict[str, Any]:
        """
        Use this tool to look up a person in the Shard building directory, when a user says they are here to meet someone. 

        Args:
            name: Full name of the person the guest is visiting
        """

        directory = {
            "Sarah Collins": {
                "company": "Shard Capital",
                "floor": 34,
            },
            "James Patel": {
                "company": "Shard Capital",
                "floor": 21,
            },
            "Emily Wong": {
                "company": "Shard capital",
                "floor": 42,
            },
        }

        if name not in directory:
            return {
                "found": False
            }

        person = directory[name]
        return {
            "found": True,
            "company": person["company"],
            "floor": person["floor"],
        }
    


    @function_tool
    async def get_building_info(
        self,
        context: RunContext,
        topic: str,
    ) -> str:
        """
        rovide information about facilities in The Shard.

        Args:
            topic: The topic requested, e.g. bathroom, lifts, waiting area
        """

        info = {
            "bathroom": "The nearest restrooms are just past the security gates on the left.",
            "waiting area": "You’re welcome to take a seat in the main lobby just behind reception.",
            "lifts": "The lifts are directly behind you. Security will direct you to the correct lift bank.",
        }

        return info.get(topic.lower(), "I can help with that, could you be a bit more specific?")


    @function_tool 
    async def get_directions(self, context: RunContext, floor: int) -> str:
        """
        Provide directions to the lifts and the correct lift bank for a given floor.

        Args:
            floor: The floor the guest is trying to reach
        """

        if floor < 1 or floor > 72:
            return "I'm sorry, but {} is not a valid floor in The Shard. Please check the directory for valid floors.".format(floor)
        
        if floor <= 10:
            return "To get to floor {}, take the lifts on the left and select the first lift bank.".format(floor)
        elif floor <= 40:
            return "To get to floor {}, take the lifts on the left and select the second lift bank.".format(floor)
        else:
            return "To get to floor {}, take the lifts on the left and select the third lift bank.".format(floor)


    @function_tool
    async def check_in(self, context: RunContext, name: str) -> str:
        """
        Check a visitor in when they arrive, and provide them with a visitor badge.

        Args:
            name: The name of the visitor checking in
        """

        list_of_visitors.append(name)
        
        return "Welcome to The Shard, {}! I have checked you in and printed a visitor badge for you. Please take a seat in the lobby while I notify your contact.".format(name)

    @function_tool
    async def check_available(self, context: RunContext, name: str) -> str:
        """
        Check if the person the visitor is meeting is currently in the building or not.

        Args:
            name: The name of the person the visitor is trying to meet
        """

        directory = {
            "Sarah Collins": {
                "in_building": True,
            },
            "James Patel": {
                "in_building": False,
            },
            "Emily Wong": {
                "in_building": True,
            },
        }

        if name not in directory:
            return "I'm sorry, but I couldn't find {} in the directory. Please check the spelling and try again.".format(name)

        if directory[name]["in_building"]:
            return "{} is currently in the building and I will notify them of your arrival.".format(name)
        else:
            return "I'm sorry, but {} is not currently in the building. Would you like me to let them know you stopped by, or would you like to wait for them to arrive?".format(name)


    @function_tool
    async def get_wait_time(self, context: RunContext, contact: str, time: str | None) -> str:
        """
        If the visitor needs to wait, provide an estimated wait time based on the time they arrived and the time of their meeting, if available.

        Args:
            contact: The person the visitor is meeting
            time: The time of the meeting, if available
        """
        if time is None:
            return "I don't have the time of your meeting, but I will let your contact know you have arrived and they can come down to meet you when they're ready. In the meantime, please take a seat in the lobby."

        current_time = fetch_time("Europe/London")["datetime"]
        wait_time = calculate_wait_time(current_time, time)

        return "The time now is {}, so the estimated wait time is {} minutes. Please take a seat in the lobby and I will let your contact know you have arrived.".format(current_time, wait_time)


def calculate_wait_time(current_time: str, meeting_time: str) -> int:
    """
    Calculate the estimated wait time in minutes based on the current time and the meeting time.

    Args:
        current_time: The current time in ISO format
        meeting_time: The time of the meeting in ISO format
    Returns:    The estimated wait time in minutes
    """

    current_time_dt = datetime.fromisoformat(current_time)
    meeting_time_dt = datetime.fromisoformat(meeting_time)

    wait_time = (meeting_time_dt - current_time_dt).total_seconds() / 60

    if wait_time < 0:
        return 0

    return int(wait_time)


def fetch_time(timezone: str) -> dict:
    """
    Fetch current time for the given timezone using WorldTimeAPI.

    :param timezone: IANA timezone like "Europe/London"
    :return: JSON response as a dictionary
    """
    url = f"https://worldtimeapi.org/api/timezone/{timezone}"

    response = requests.get(url, timeout=5)
    response.raise_for_status()  

    return response.json()



def imperial_to_metric(temp_f: float) -> float:
    """Convert a temperature from Fahrenheit to Celsius."""
    return (temp_f - 32) * 5.0 / 9.0

server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def my_agent(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=inference.STT(model="deepgram/nova-3", language="multi"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=inference.TTS(
            model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
        ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


# if __name__ == "__main__":
#     import asyncio
#     from livekit.agents import AgentSession, inference

#     async def demo():
#         async with inference.LLM(model="openai/gpt-4.1-mini") as llm, AgentSession(llm=llm) as session:
#             await session.start(Assistant())
#             while True:
#                 user_input = input("You: ")
#                 if user_input.lower() in {"quit", "exit"}:
#                     break
#                 result = await session.run(user_input=user_input)
#                 async for event in result.events():
#                     if event.type == "message" and event.message.role == "assistant":
#                         print("Agent:", event.message.content)

#     asyncio.run(demo())

if __name__ == "__main__":
    cli.run_app(server)