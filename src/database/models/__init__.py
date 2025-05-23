"""
MongoDB models for the application.
"""

from .messages import Message, get_messages_collection
from .reports import Report, get_reports_collection
from .invitation_code_model import InvitationCode, InvitationCodeCreate 