from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional


# I've created this class instead of using the memory saver, because I do not want persistent memory for this use case. 
# This was easier to implement for a smaller demo. However, I'd use a better memory manager class for an actual app, 
# Right now I am just appending all context, there is no summarization, no truncation

class Message(BaseModel):
    role: str
    content: str

class MessagesMemory(BaseModel):
    """ Stores conversation context for the conversation """

    messages: List[Message] = Field(default_factory=list)
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    
    def add_message(self, role: str, content: str) -> None:
        """ Add a message to the conversation history """

        self.messages.append(Message(role=role, content=content))
    
    def get_message_history(self, n: int = 10) -> str:
        """ Get the message history and format in the LLM prompt format """

        messages = self.messages[-n:]
        return "\n".join([f"{msg.role}: {msg.content}" for msg in messages])
    
    def update_entity(self, key: str, value: Any) -> None:
        """ Update an extracted entity : tokens, addresses, etc"""

        self.extracted_entities[key] = value
    
    def get_entity(self, key: str) -> Optional[Any]:
        """ Get an extracted entity"""
        
        return self.extracted_entities.get(key)
    
    def reset(self) -> None:
        """ Clear all memory"""
        self.messages.clear()
        self.extracted_entities.clear()