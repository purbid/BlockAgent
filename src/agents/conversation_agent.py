import os
import langchain
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional
from langchain_core.caches import InMemoryCache
from langchain_core.globals import set_llm_cache

langchain.llm_cache = InMemoryCache()
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage


load_dotenv()

MODEL_NAME = "gpt-4o-mini"
OPENAI_KEY  = os.getenv('OPENAI_KEY')

from src.memory.memory_utils import MessagesMemory

class ConversationAgent:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_KEY)
        self.conversational_llm = ChatOpenAI(
            model_name = MODEL_NAME,
            openai_api_key  = OPENAI_KEY, 
            temperature=0, 
        )

    def make_conversation(self, query: str, memory: MessagesMemory, state) -> Dict[str, Any]:

        print("here to conversational agent")
       
        system_prompt = """
                You are BlockAgent, a specialized AI assistant designed to help users with cryptocurrency and DeFi queries.
                Your role is to assist with:
                1. Data retrieval from the uniswap subgraph (e.g., token prices, liquidity pools, trading volumes, protocol info).
                2. Transaction-related tasks (e.g., simulating swaps, checking balances, estimating gas fees).
                3. Providing general crypto and DeFi education.

                Do NOT identify yourself as a general AI or mention being developed by OpenAI. 
                Focus entirely on your identity as BlockAgent and your crypto/DeFi expertise. 
                If the user asks about any othet topic, you will not engage, strictly limit the conversation to 
                DeFi queries and your capabilites as BlockAgent
                Respond in a friendly, conversational tone, and always tie your answers back to your capabilities when relevant, and always be concise."""

        print("lead to the conversational agent")
        conversation_history = memory.get_message_history()

        messages = [SystemMessage(content=system_prompt),
                    HumanMessage(content=conversation_history + "\n" + query)]
        
        response = self.conversational_llm.invoke(messages)
        conversation_response = response.content
       
        memory.add_message("assistant", conversation_response)

        return {
            **state, 
            "agent_response": conversation_response,
            "status": "conversation_processed"
        }
