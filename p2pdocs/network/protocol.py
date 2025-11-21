"""
Network Protocol Module - Message definitions and serialization
Phase 2: TCP Socket Communication foundation
"""

import json
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime


class MessageType(Enum):
    """Message types for P2P communication"""
    # Peer management
    PEER_ANNOUNCE = "peer_announce"           # Announce presence to peer
    PEER_HEARTBEAT = "peer_heartbeat"         # Keep-alive signal
    PEER_DISCONNECT = "peer_disconnect"       # Graceful disconnect
    
    # Document operations
    KEYSTROKE = "keystroke"                   # Real-time keystroke
    DOCUMENT_LOCK_REQUEST = "doc_lock_req"   # Request edit lock
    DOCUMENT_LOCK_GRANT = "doc_lock_grant"   # Grant edit lock
    DOCUMENT_LOCK_RELEASE = "doc_lock_release"  # Release edit lock
    
    # Synchronization
    SYNC_REQUEST = "sync_request"             # Request full sync
    SYNC_RESPONSE = "sync_response"           # Send document state
    UPDATE_NOTIFICATION = "update_notification"  # Notify of changes
    
    # Error handling
    ERROR = "error"                           # Error message
    ACK = "ack"                              # Acknowledgment


@dataclass
class Message:
    """Represents a P2P message"""
    msg_type: MessageType
    sender: str                    # Username of sender
    recipient: str                # Username of recipient (or "*" for broadcast)
    document: Optional[str] = None # Document name (if applicable)
    payload: Optional[Dict[str, Any]] = None  # Message-specific data
    timestamp: str = None         # ISO format timestamp
    msg_id: Optional[str] = None  # Unique message identifier
    
    def __post_init__(self):
        """Initialize defaults"""
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.msg_id is None:
            self.msg_id = f"{self.sender}_{self.timestamp}"
        if self.payload is None:
            self.payload = {}
    
    def to_json(self) -> str:
        """Serialize message to JSON string"""
        data = asdict(self)
        # Convert enum to string
        data['msg_type'] = self.msg_type.value
        return json.dumps(data)
    
    @staticmethod
    def from_json(json_str: str) -> 'Message':
        """Deserialize message from JSON string"""
        try:
            data = json.loads(json_str)
            # Convert string back to enum
            data['msg_type'] = MessageType(data['msg_type'])
            return Message(**data)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            raise ValueError(f"Invalid message format: {str(e)}")
    
    def __repr__(self) -> str:
        """String representation for debugging"""
        return f"Message(type={self.msg_type.value}, sender={self.sender}, doc={self.document})"


class MessageBuilder:
    """Builder pattern for constructing messages"""
    
    @staticmethod
    def peer_announce(sender: str, username: str, port: int) -> Message:
        """Build a peer announcement message"""
        return Message(
            msg_type=MessageType.PEER_ANNOUNCE,
            sender=sender,
            recipient="*",
            payload={"username": username, "port": port}
        )
    
    @staticmethod
    def heartbeat(sender: str) -> Message:
        """Build a heartbeat message"""
        return Message(
            msg_type=MessageType.PEER_HEARTBEAT,
            sender=sender,
            recipient="*"
        )
    
    @staticmethod
    def keystroke(sender: str, document: str, char: str, position: int) -> Message:
        """Build a keystroke message"""
        return Message(
            msg_type=MessageType.KEYSTROKE,
            sender=sender,
            recipient="*",
            document=document,
            payload={"character": char, "position": position}
        )
    
    @staticmethod
    def lock_request(sender: str, document: str) -> Message:
        """Build a document lock request"""
        return Message(
            msg_type=MessageType.DOCUMENT_LOCK_REQUEST,
            sender=sender,
            recipient="*",
            document=document,
            payload={"request_time": datetime.now().isoformat()}
        )
    
    @staticmethod
    def lock_grant(sender: str, document: str, recipient: str, lock_duration: int = 300) -> Message:
        """Build a lock grant message"""
        return Message(
            msg_type=MessageType.DOCUMENT_LOCK_GRANT,
            sender=sender,
            recipient=recipient,
            document=document,
            payload={"duration_seconds": lock_duration}
        )
    
    @staticmethod
    def lock_release(sender: str, document: str) -> Message:
        """Build a lock release message"""
        return Message(
            msg_type=MessageType.DOCUMENT_LOCK_RELEASE,
            sender=sender,
            recipient="*",
            document=document
        )
    
    @staticmethod
    def sync_request(sender: str, document: str, from_version: int = 0) -> Message:
        """Build a sync request"""
        return Message(
            msg_type=MessageType.SYNC_REQUEST,
            sender=sender,
            recipient="*",
            document=document,
            payload={"from_version": from_version}
        )
    
    @staticmethod
    def sync_response(sender: str, document: str, content: str, version: int) -> Message:
        """Build a sync response"""
        return Message(
            msg_type=MessageType.SYNC_RESPONSE,
            sender=sender,
            recipient="*",
            document=document,
            payload={"content": content, "version": version}
        )
    
    @staticmethod
    def error(sender: str, error_msg: str, original_msg: Optional[Message] = None) -> Message:
        """Build an error message"""
        payload = {"error": error_msg}
        if original_msg:
            payload["original_type"] = original_msg.msg_type.value
        
        return Message(
            msg_type=MessageType.ERROR,
            sender=sender,
            recipient="*",
            payload=payload
        )
    
    @staticmethod
    def ack(sender: str, msg_id: str) -> Message:
        """Build an acknowledgment message"""
        return Message(
            msg_type=MessageType.ACK,
            sender=sender,
            recipient="*",
            payload={"ack_msg_id": msg_id}
        )
