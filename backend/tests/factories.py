"""Factories for incidental values in Pydantic boundary-model tests."""

from polyfactory.factories.pydantic_factory import ModelFactory

from curlchat.services.conversation_service import ConversationMetadata
from curlchat.services.visualization_service import VisualizationArtifact


class ConversationMetadataFactory(ModelFactory[ConversationMetadata]):
    __model__ = ConversationMetadata


class VisualizationArtifactFactory(ModelFactory[VisualizationArtifact]):
    __model__ = VisualizationArtifact
