from datetime import datetime
from typing import Optional, cast, List, Dict, Union
from opencopilot_db import ChatHistory, engine, pdf_data_source_model
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy import distinct
from sqlalchemy.orm import class_mapper
from langchain.schema import BaseMessage, AIMessage, HumanMessage

Session = sessionmaker(bind=engine)


def create_chat_history(
    chatbot_id: str,
    session_id: str,
    from_user: str,
    message: str,
) -> ChatHistory:
    """Creates a new chat history record.

    Args:
      chatbot_id: The ID of the chatbot that sent the message.
      session_id: The ID of the chat session.
      from_user: The user who sent the message.
      message: The message content.

    Returns:
      The newly created ChatHistory object.
    """

    with Session() as session:
        chat_history = ChatHistory(
            chatbot_id=chatbot_id,
            session_id=session_id,
            from_user=from_user,
            message=message,
        )

        session.add(chat_history)
        session.commit()

    return chat_history


def get_all_chat_history_by_session_id(
    session_id: str, limit: int = 20, offset: int = 0
) -> List[ChatHistory]:
    """Retrieves all chat history records for a given session ID, sorted by created_at in descending order (most recent first).

    Args:
      session_id: The ID of the session to retrieve chat history for.
      limit: The maximum number of chat history records to retrieve.
      offset: The offset at which to start retrieving chat history records.

    Returns:
      A list of ChatHistory objects, sorted by created_at in descending order.
    """
    session = Session()
    chats = (
        session.query(ChatHistory)
        .filter_by(session_id=session_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )

    # Sort the chat history records by created_at in descending order.
    chats.sort(key=lambda chat: chat.created_at)

    return chats


def get_chat_message_as_llm_conversation(session_id: str) -> List[BaseMessage]:
    chats = get_all_chat_history_by_session_id(session_id, 100)
    conversations: List[BaseMessage] = []
    for chat in chats:
        if chat.from_user == True:
            conversations.append(HumanMessage(content=chat.message))
        elif chat.from_user == False:
            conversations.append(AIMessage(content=chat.message))

    return conversations


def get_all_chat_history(limit: int = 10, offset: int = 0) -> List[ChatHistory]:
    """Retrieves all chat history records.

    Args:
      limit: The maximum number of chat history records to retrieve.
      offset: The offset at which to start retrieving chat history records.

    Returns:
      A list of ChatHistory objects.
    """
    with Session() as session:
        chats = session.query(ChatHistory).limit(limit).offset(offset).all()
        return chats


def update_chat_history(
    chat_history_id: str,
    chatbot_id: Optional[str] = None,
    session_id: Optional[str] = None,
    from_user: Optional[str] = None,
    message: Optional[str] = None,
) -> ChatHistory:
    """Updates a chat history record.

    Args:
      chat_history_id: The ID of the chat history record to update.
      chatbot_id: The new chatbot ID.
      session_id: The new session ID.
      from_user: The new user name.
      message: The new message content.

    Returns:
      The updated ChatHistory object.
    """
    with Session() as session:
        chat_history: ChatHistory = session.query(ChatHistory).get(chat_history_id)

        if chatbot_id is not None:
            chat_history.chatbot_id = chatbot_id
        if session_id is not None:
            chat_history.session_id = session_id
        if from_user is not None:
            chat_history.from_user = from_user
        if message is not None:
            chat_history.message = message

        chat_history.updated_at = datetime.now()

        session.add(chat_history)
        session.commit()

    return chat_history


def delete_chat_history(chat_history_id: str) -> None:
    """Deletes a chat history record.

    Args:
      chat_history_id: The ID of the chat history record to delete.
    """
    with Session() as session:
        chat_history = session.query(ChatHistory).get(chat_history_id)
        session.delete(chat_history)
        session.commit()


def get_chat_history_for_retrieval_chain(
    session_id: str, limit: Optional[int] = None
) -> List[Tuple[str, str]]:
    """Fetches limited ChatHistory entries by session ID and converts to chat_history format.

    Args:
        session_id (str): The session ID to fetch chat history for
        limit (int, optional): Maximum number of entries to retrieve

    Returns:
        list[tuple[str, str]]: List of tuples of (user_query, bot_response)
    """
    with Session() as session:
        # Query and limit results if a limit is provided
        query = (
            session.query(ChatHistory)
            .filter(ChatHistory.session_id == session_id)  # Fixed filter condition
            .order_by(ChatHistory.created_at)  # Fixed order_by condition
        )
        if limit:
            query = query.limit(limit)  # Fixed limit condition

        chat_history = []

        user_query = None
        for entry in query:
            if entry.from_user:
                user_query = entry.message
            else:
                if user_query is not None:
                    chat_history.append((user_query, entry.message))
                    user_query = None

    return chat_history


def get_unique_sessions_with_first_message_by_bot_id(
    bot_id: str, limit: int = 20, offset: int = 0
) -> List[Dict[str, Union[str, Optional[ChatHistory]]]]:
    """
    Retrieve unique session_ids for a given bot_id with pagination,
    along with the first message in each session.

    Args:
        bot_id (str): The bot_id for which to retrieve session_ids.
        limit (int, optional): The maximum number of results to return. Defaults to 20.
        offset (int, optional): The number of results to skip from the beginning. Defaults to 0.
        session (Session, optional): The SQLAlchemy session. Defaults to None.

    Returns:
        List[Dict[str, Union[str, Optional[ChatHistory]]]]: A list of dictionaries containing
        unique session_ids and their first messages.
    """
    # If a session is not provided, create a new one
    session = Session()

    # Use distinct to get unique session_ids
    unique_session_ids = (
        session.query(distinct(ChatHistory.session_id))
        .filter_by(chatbot_id=bot_id)
        .limit(limit)
        .offset(offset)
        .all()
    )

    result_list = []

    for session_id in unique_session_ids:
        # Get the first message in each session
        first_message = (
            session.query(ChatHistory)
            .filter_by(chatbot_id=bot_id, session_id=session_id[0])
            .order_by(ChatHistory.created_at.asc())
            .first()
        )

        # Convert ChatHistory object to a dictionary
        if first_message:
            first_message_dict = {
                column.key: getattr(first_message, column.key)
                for column in class_mapper(ChatHistory).mapped_table.columns
            }
        else:
            first_message_dict = None

        # Create a dictionary with session_id and first_message
        result_dict = {"session_id": session_id[0], "first_message": first_message_dict}

        result_list.append(result_dict)

    return result_list
