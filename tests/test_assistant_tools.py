from livekit.agents import AgentSession, inference, llm
from agent import Assistant
import pytest
from unittest.mock import patch


def _llm() -> llm.LLM:
    return inference.LLM(model="openai/gpt-4.1-mini")



@pytest.mark.asyncio
async def test_weather_london() -> None:
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="What's the weather like in London today?"
        )

        # First: the agent should call the weather tool
        await (
            result.expect.next_event()
            .is_function_call(name="lookup_weather")
        )


        # Then: the assistant should explain the weather clearly
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                Says what the weather is like in London today.
                Mentions a temperature.
                Sounds natural and helpful.
                """,
            )
        )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_weather_unknown_city() -> None:
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="Can you tell me the weather in Paris?"
        )

        await (
            result.expect.next_event()
            .is_function_call(name="lookup_weather")
        )

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                Politely explains that the weather for Paris is unavailable.
                Does not invent weather data.
                """,
            )
        )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_directory_lookup_found_and_wait_time() -> None:
    fake_time = {
        "datetime": "2026-01-01T09:50:00"
    }

    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(Assistant())

        # Mock external time API
        with patch("agent.fetch_time", return_value=fake_time):
            result = await session.run(
                user_input="I have a meeting with Sarah Collins at 10:00 AM."
            )

        # 1️⃣ Agent checks directory
        await (
            result.expect.next_event()
            .is_function_call(name="lookup_directory")
            .judge(
                llm,
                intent="""
                Looks up Sarah Collins in the building directory.
                """,
            )
        )

        # 2️⃣ Agent checks availability
        await (
            result.expect.next_event()
            .is_function_call(name="check_available")
            .judge(
                llm,
                intent="""
                Checks whether Sarah Collins is currently in the building.
                """,
            )
        )

        # 3️⃣ Agent calculates wait time
        await (
            result.expect.next_event()
            .is_function_call(name="get_wait_time")
            .judge(
                llm,
                intent="""
                Calculates how long the visitor will need to wait
                based on the current time and meeting time.
                """,
            )
        )

        # 4️⃣ Agent explains everything clearly to the visitor
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                Confirms that Sarah Collins is in the directory.
                Confirms she is in the building.
                Provides an estimated wait time.
                Uses a polite, professional receptionist tone.
                Gives clear instructions on what the visitor should do next.
                """,
            )
        )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_directory_lookup_not_found() -> None:
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="I'm here to see John Doe."
        )

        await (
            result.expect.next_event()
            .is_function_call(name="lookup_directory")
        )

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                Explains politely that the person is not in the directory.
                Does not hallucinate a company or floor.
                Offers help or next steps.
                """,
            )
        )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_building_info_bathroom() -> None:
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="Where are the bathrooms?"
        )

        await (
            result.expect.next_event()
            .is_function_call(name="get_building_info")
        )

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                Clearly explains where the restrooms are.
                Uses calm, receptionist-like language.
                """,
            )
        )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_building_info_cafeteria() -> None:
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="Is there a cafeteria here?"
        )

        await (
            result.expect.next_event()
            .is_function_call(name="get_building_info")
        )

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                Explains there is not a cafeteria in the building.
                Does not hallucinate a cafeteria or food options.
                Uses calm, receptionist-like language.
                """,
            )
        )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_get_directions() -> None:
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="How do I get to floor 5?"
        )

        await (
            result.expect.next_event()
            .is_function_call(name="get_directions")
        )

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                Provides clear, step-by-step directions from the lobby to the conference room.
                Uses calm, receptionist-like language.
                """,
            )
        )

        result.expect.no_more_events()


@pytest.mark.asyncio
async def test_get_directions_unknown_floor() -> None:
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(Assistant())

        result = await session.run(
            user_input="How do I get to floor 100?"
        )

        await (
            result.expect.next_event()
            .is_function_call(name="get_directions")
        )

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                Politely explains that floor 100 does not exist in the building.
                Does not hallucinate directions or features of a non-existent floor.
                Uses calm, receptionist-like language.
                """,
            )
        )

        result.expect.no_more_events()