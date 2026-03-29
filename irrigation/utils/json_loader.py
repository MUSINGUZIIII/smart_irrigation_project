import json
import os
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class JSONIntentLoader:
    """Load and manage JSON intent files for the chatbot"""

    def __init__(self):
        self.intents = {}
        self.load_all_intents()

    def load_all_intents(self):
        """Load all JSON intent files from the chatbot_data directory"""
        chatbot_data_dir = os.path.join(settings.BASE_DIR, 'irrigation', 'chatbot_data')

        if not os.path.exists(chatbot_data_dir):
            logger.warning(f"Chatbot data directory not found: {chatbot_data_dir}")
            return

        json_files = {
            'help': 'help_intents.json',
            'contact': 'contact_intents.json',
            'privacy': 'privacy_intents.json',
            'terms': 'terms_intents.json',
            'system': 'system_intents.json'
        }

        for category, filename in json_files.items():
            file_path = os.path.join(chatbot_data_dir, filename)
            try:
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.intents[category] = json.load(f)
                    logger.info(f"Loaded {category} intents from {filename}")
                else:
                    logger.warning(f"JSON file not found: {file_path}")
            except Exception as e:
                logger.error(f"Error loading {filename}: {str(e)}")

    def get_intent(self, category):
        """Get intents for a specific category"""
        return self.intents.get(category, {})

    def get_all_intents(self):
        """Get all loaded intents"""
        return self.intents

    def reload_intents(self):
        """Reload all intents from files"""
        self.intents = {}
        self.load_all_intents()
        return self.intents

    def find_matching_intent(self, query, threshold=0.6):
        """
        Find the best matching intent for a query
        Returns: (intent_data, category, score)
        """
        query_lower = query.lower().strip()
        best_match = None
        best_score = 0
        best_category = None

        for category, data in self.intents.items():
            for intent in data.get('intents', []):
                score = self._calculate_match_score(query_lower, intent)
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = intent
                    best_category = category

        return best_match, best_category, best_score

    def _calculate_match_score(self, query, intent):
        """Calculate match score between query and intent patterns"""
        max_score = 0

        for pattern in intent.get('patterns', []):
            pattern_lower = pattern.lower()

            # Exact match gets highest score
            if query == pattern_lower:
                return 1.0

            # Check if pattern is contained in query or vice versa
            if pattern_lower in query or query in pattern_lower:
                score = 0.8
            else:
                # Calculate word overlap score
                query_words = set(query.split())
                pattern_words = set(pattern_lower.split())
                common_words = query_words & pattern_words

                if common_words:
                    score = len(common_words) / max(len(query_words), len(pattern_words)) * 0.6
                else:
                    score = 0

            max_score = max(max_score, score)

        return max_score

    def get_response(self, query):
        """Get response for a query using intent matching"""
        intent, category, score = self.find_matching_intent(query)

        if intent and score >= 0.6:
            response = {
                'matched': True,
                'type': 'json_intent',
                'category': category,
                'intent': intent['tag'],
                'response': self._get_random_response(intent['responses']),
                'confidence': score,
                'suggestions': self._generate_suggestions(intent['tag'])
            }
        else:
            response = {
                'matched': False,
                'response': "I'm not sure how to help with that. Could you try rephrasing your question?",
                'confidence': 0,
                'suggestions': self._get_fallback_suggestions()
            }

        return response

    def _get_random_response(self, responses):
        """Get a random response from the responses list"""
        import random
        return random.choice(responses) if responses else "I'm here to help!"

    def _generate_suggestions(self, intent_tag):
        """Generate related suggestions based on intent"""
        suggestions_map = {
            'user_manual': ["Download manual", "Setup instructions", "Troubleshooting"],
            'watering_frequency': ["Soil moisture", "Weather-based watering", "Schedule setup"],
            'contact_support': ["Phone support", "Email support", "Visit location"],
            'emergency_procedure': ["Emergency stop", "System reset", "Contact support"],
            'privacy_policy': ["Data collection", "Data usage", "Data security"]
        }
        return suggestions_map.get(intent_tag, ["How can I help?", "System status", "Control panel"])

    def _get_fallback_suggestions(self):
        """Get fallback suggestions when no intent matches"""
        return [
            "How to control the pump?",
            "Show me the dashboard",
            "Emergency procedures",
            "Contact support"
        ]
