from difflib import get_close_matches
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.functional import lazy
from enum import Enum
import logging
import random
from datetime import datetime, timedelta
import json
from typing import Dict, List, Tuple, Optional, Any, Set
import Levenshtein
import re
from irrigation.utils.json_loader import JSONIntentLoader

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Enumeration for different resource types in the help system"""
    ROUTE = 'route'
    INFO = 'info'
    COMMAND = 'command'
    WIDGET = 'widget'
    HELP = 'help'
    CHAT = 'chat'
    TUTORIAL = 'tutorial'
    TROUBLESHOOTING = 'troubleshooting'
    CONTACT = 'contact'
    EMERGENCY = 'emergency'
    NAVIGATION = 'navigation'


class SpellingCorrector:
    """Advanced spelling correction system with irrigation-specific vocabulary"""

    def __init__(self):
        # Irrigation-specific dictionary with common terms and their weights
        self.irrigation_terms = {
            # High frequency terms
            'pump': 10, 'valve': 10, 'water': 10, 'irrigation': 10, 'system': 9,
            'schedule': 9, 'zone': 9, 'moisture': 8, 'sensor': 8, 'dashboard': 8,
            'control': 8, 'emergency': 8, 'stop': 8, 'settings': 7, 'analytics': 7,
            'status': 7, 'threshold': 7, 'manual': 7, 'automatic': 7, 'help': 6,

            # Medium frequency terms
            'pressure': 6, 'flow': 6, 'timer': 6, 'sprinkler': 6, 'pipe': 5,
            'nozzle': 5, 'filter': 5, 'pipeline': 5, 'drip': 5, 'spray': 5,
            'weather': 5, 'rain': 5, 'forecast': 5, 'humidity': 5, 'temperature': 5,

            # Command terms
            'start': 6, 'stop': 6, 'open': 6, 'close': 6, 'activate': 6,
            'deactivate': 6, 'set': 6, 'change': 6, 'adjust': 6, 'check': 6,
            'view': 6, 'show': 6, 'display': 6, 'monitor': 6, 'test': 5,

            # Troubleshooting terms
            'problem': 7, 'issue': 7, 'error': 7, 'fix': 7, 'repair': 7,
            'broken': 7, 'leak': 7, 'clog': 7, 'blockage': 6, 'malfunction': 6,
        }

        # Common misspellings and their corrections
        self.common_misspellings = {
            'pum': 'pump', 'valv': 'valve', 'irigation': 'irrigation',
            'moistre': 'moisture', 'scedule': 'schedule', 'dashbord': 'dashboard',
            'controll': 'control', 'emergancy': 'emergency', 'threshhold': 'threshold',
            'analitics': 'analytics', 'manualy': 'manually', 'automaticaly': 'automatically',
            'nozle': 'nozzle', 'sprinkeler': 'sprinkler', 'preassure': 'pressure',
            'temprature': 'temperature', 'humidty': 'humidity', 'forcast': 'forecast'
        }

    def correct_spelling(self, query: str) -> Tuple[str, List[str]]:
        """
        Correct spelling errors in the query and return the corrected query
        along with a list of corrections made
        """
        original_query = query
        corrections = []

        # First, check for common misspellings
        words = query.split()
        corrected_words = []

        for word in words:
            lower_word = word.lower()

            # Check if it's a common misspelling
            if lower_word in self.common_misspellings:
                correction = self.common_misspellings[lower_word]
                # Preserve original case if it was capitalized
                if word[0].isupper():
                    correction = correction.capitalize()
                corrected_words.append(correction)
                corrections.append(f"'{word}' → '{correction}'")
                continue

            # Check if word is in our irrigation terms (case insensitive)
            if lower_word not in [term.lower() for term in self.irrigation_terms.keys()]:
                # Find closest match using Levenshtein distance
                best_match = None
                best_distance = float('inf')

                for term in self.irrigation_terms.keys():
                    distance = Levenshtein.distance(lower_word, term.lower())
                    if distance < best_distance and distance <= 2:  # Allow up to 2 character differences
                        best_distance = distance
                        best_match = term

                if best_match:
                    # Preserve original case if it was capitalized
                    correction = best_match if word.islower() else best_match.capitalize()
                    corrected_words.append(correction)
                    corrections.append(f"'{word}' → '{correction}'")
                    continue

            # If no correction needed, keep the original word
            corrected_words.append(word)

        corrected_query = " ".join(corrected_words)

        return corrected_query, corrections


class IrrigationGuide:
    """Intelligent help system for irrigation management application with JSON integration"""

    def __init__(self):
        try:
            self.spelling_corrector = SpellingCorrector()
            self.json_loader = JSONIntentLoader()
            self.resources = {
                ResourceType.ROUTE: self._load_knowledge(),
                ResourceType.INFO: self._load_informational_pages(),
                ResourceType.COMMAND: self._load_control_commands(),
                ResourceType.WIDGET: self._load_dashboard_widgets(),
                ResourceType.HELP: self._load_help_resources(),
                ResourceType.CHAT: self._load_chat_responses(),
                ResourceType.TUTORIAL: self._load_tutorials(),
                ResourceType.TROUBLESHOOTING: self._load_troubleshooting_guides(),
                ResourceType.CONTACT: self._load_contact_information(),
                ResourceType.EMERGENCY: self._load_emergency_resources(),
                ResourceType.NAVIGATION: self._load_navigation_guides()
            }
            self.user_context = {}
            self.conversation_history = []
            self.user_preferences = {}
        except Exception as e:
            logger.error(f"Error initializing IrrigationGuide: {str(e)}")
            self.resources = {rt: {} for rt in ResourceType}
            self.json_loader = JSONIntentLoader()

    def _lazy_reverse(self, view_name):
        """Lazy version of reverse to avoid URL resolution during import"""
        try:
            return lazy(reverse, str)(view_name)
        except:
            # Fallback for URL resolution errors
            return lazy(lambda: '/', str)()

    def _load_knowledge(self):
        """Load application routes and navigation information with lazy URLs"""
        return {
            "dashboard": {
                "url": self._lazy_reverse('dashboard'),
                "description": "Main system dashboard showing current status, sensor readings, and system overview with real-time updates",
                "keywords": ["dashboard", "home", "main page", "status", "overview", "homepage", "main"],
                "icon": "fa-tachometer-alt",
                "category": "Monitoring",
                "importance": 10,
                "navigation_instructions": "Click on the 'Dashboard' tab in the main navigation menu at the top of the page to view your system overview."
            },
            "control panel": {
                "url": self._lazy_reverse('control-panel'),
                "description": "Manual control center for pumps, valves, and irrigation zones with real-time adjustments and scheduling",
                "keywords": ["control", "manual", "pump", "valve", "switch", "manual control", "controls"],
                "icon": "fa-sliders-h",
                "category": "Control",
                "importance": 9,
                "navigation_instructions": "Go to the header menu and click on 'Control Panel' to access manual controls for your irrigation system."
            },
            "analytics": {
                "url": self._lazy_reverse('visualize-data'),
                "description": "Advanced analytics with charts, graphs, and historical irrigation data visualization",
                "keywords": ["analytics", "charts", "graphs", "history", "data", "statistics", "reports"],
                "icon": "fa-chart-line",
                "category": "Analysis",
                "importance": 8,
                "navigation_instructions": "In the header, click on 'Analytics' to view detailed charts and reports about your irrigation system."
            },
            "download data": {
                "url": self._lazy_reverse('dashboard'),
                "description": "Export sensor data as CSV or Excel files for further analysis and reporting",
                "keywords": ["download", "export", "get data", "csv", "excel", "export data", "download data"],
                "icon": "fa-file-export",
                "category": "Data",
                "importance": 7,
                "navigation_instructions": "Navigate to Analytics → Export Data to download your irrigation data."
            },
            "help": {
                "url": self._lazy_reverse('help'),
                "description": "Comprehensive documentation, user guides, and support resources",
                "keywords": ["help", "support", "documentation", "faq", "guide", "manual"],
                "icon": "fa-question-circle",
                "category": "Support",
                "importance": 6,
                "navigation_instructions": "Click the help icon (?) in the top right corner or visit the Help section from the main menu."
            },
            "privacy": {
                "url": self._lazy_reverse('privacy'),
                "description": "Our privacy policy and data handling practices for your security",
                "keywords": ["privacy", "policy", "data", "protection", "security"],
                "icon": "fa-shield-alt",
                "category": "Legal",
                "importance": 3,
                "navigation_instructions": "Scroll to the footer and click 'Privacy Policy' or visit Settings → Legal."
            },
            "terms": {
                "url": self._lazy_reverse('terms'),
                "description": "Terms of service and usage agreement for the irrigation system",
                "keywords": ["terms", "service", "agreement", "legal", "conditions"],
                "icon": "fa-file-contract",
                "category": "Legal",
                "importance": 2,
                "navigation_instructions": "Scroll to the footer and click 'Terms of Service' or visit Settings → Legal."
            },
            "about": {
                "url": self._lazy_reverse('about'),
                "description": "Learn about our irrigation system, development team, and achievements",
                "keywords": ["about", "information", "team", "developer", "company"],
                "icon": "fa-info-circle",
                "category": "Information",
                "importance": 4,
                "navigation_instructions": "Click on 'About' in the footer or navigate via the Help section."
            },
            "contact": {
                "url": self._lazy_reverse('contact'),
                "description": "Get in touch with our support team for assistance and inquiries",
                "keywords": ["contact", "support", "help", "email", "phone", "contact us"],
                "icon": "fa-envelope",
                "category": "Support",
                "importance": 5,
                "navigation_instructions": "Click 'Contact Us' in the footer or go to Help → Contact Support."
            },
            "profile": {
                "url": self._lazy_reverse('profile'),
                "description": "Manage your user account settings, preferences, and notification options",
                "keywords": ["profile", "account", "settings", "user", "preferences"],
                "icon": "fa-user",
                "category": "Account",
                "importance": 7,
                "navigation_instructions": "Click on your profile picture in the top right corner and select 'Profile Settings'."
            },
            "chatbot": {
                "url": self._lazy_reverse('ask_chatbot'),
                "description": "Interactive AI assistant for help with irrigation system management",
                "keywords": ["chat", "bot", "assistant", "help", "ask", "ai", "assistant"],
                "icon": "fa-robot",
                "category": "Support",
                "importance": 8,
                "navigation_instructions": "Click the chat icon in the bottom right corner or go to Help → Chat Assistant."
            },
            "scheduling": {
                "url": self._lazy_reverse('control-panel'),
                "description": "Create and manage irrigation schedules based on time, weather, or soil conditions",
                "keywords": ["schedule", "timer", "plan", "automatic", "watering schedule"],
                "icon": "fa-calendar-alt",
                "category": "Control",
                "importance": 8,
                "navigation_instructions": "Go to Control Panel → Scheduling tab to set up your irrigation schedules."
            },
            "zones": {
                "url": self._lazy_reverse('control-panel'),
                "description": "Configure and manage different irrigation zones for targeted watering",
                "keywords": ["zones", "areas", "sections", "zone management"],
                "icon": "fa-map-marker-alt",
                "category": "Control",
                "importance": 7,
                "navigation_instructions": "Navigate to Control Panel → Zones management to configure your irrigation zones."
            }
        }

    def _load_navigation_guides(self):
        """Load navigation guides for helping users find features"""
        return {
            "header navigation": {
                "title": "Using the Header Navigation",
                "description": "Learn how to navigate through the irrigation system using the header menu",
                "steps": [
                    "Look at the top of the page for the navigation bar",
                    "Click on any menu item to navigate to that section",
                    "Use the dropdown menus for additional options",
                    "The active section is highlighted for easy reference"
                ],
                "icon": "fa-bars",
                "category": "Navigation"
            },
            "emergency access": {
                "title": "Quick Emergency Access",
                "description": "How to quickly access emergency features from anywhere in the system",
                "steps": [
                    "Look for the red emergency button in the header",
                    "Click it to immediately access emergency controls",
                    "Alternatively, use the quick shortcuts in the dashboard",
                    "Emergency options are always accessible from any page"
                ],
                "icon": "fa-exclamation-triangle",
                "category": "Emergency"
            },
            "dashboard overview": {
                "title": "Understanding Your Dashboard",
                "description": "Learn how to interpret and use your irrigation system dashboard",
                "steps": [
                    "The main dashboard shows system status at a glance",
                    "Widgets can be rearranged by dragging them",
                    "Click on any widget for more detailed information",
                    "Use the filter options to customize your view"
                ],
                "icon": "fa-tachometer-alt",
                "category": "Navigation"
            }
        }

    def _load_control_commands(self):
        """Load system control commands with enhanced details"""
        commands = {
            "pump": {
                "description": "Control the main water pump (turn on/off) for the entire irrigation system",
                "keywords": ["pump", "water pump", "activate pump", "main pump", "water supply"],
                "icon": "fa-tint",
                "parameters": {
                    "state": {
                        "type": "boolean",
                        "description": "True to turn on, False to turn off",
                        "required": True
                    }
                },
                "examples": [
                    "Turn on the pump",
                    "Activate water pump",
                    "Stop the pump",
                    "Set pump to ON",
                    "Start main water pump"
                ],
                "safety_note": "Ensure water supply is available before activating pump",
                "navigation_instructions": "Go to Control Panel → Pumps section → Use the toggle switch to control the pump"
            },
            "valve": {
                "description": "Control individual irrigation valves (open/close) for specific zones",
                "keywords": ["valve", "water valve", "open valve", "close valve", "irrigation valve"],
                "icon": "fa-faucet",
                "parameters": {
                    "zone": {
                        "type": "number",
                        "description": "Zone number (1-8)",
                        "required": True
                    },
                    "state": {
                        "type": "boolean",
                        "description": "True to open, False to close",
                        "required": True
                    }
                },
                "examples": [
                    "Open valve for zone 1",
                    "Close irrigation valve 3",
                    "Turn on zone 2 valve",
                    "Activate valve in area 4"
                ],
                "navigation_instructions": "Navigate to Control Panel → Valves section → Select your zone → Use the control buttons"
            },
            "emergency": {
                "description": "Activate or deactivate emergency stop (immediately shuts down all systems)",
                "keywords": ["emergery", "stop", "shutdown", "safety", "emergency stop", "kill switch"],
                "icon": "fa-exclamation-triangle",
                "parameters": {
                    "activate": {
                        "type": "boolean",
                        "description": "True to activate emergency stop, False to reset",
                        "required": True
                    }
                },
                "safety_warning": "EMERGENCY STOP will immediately shut down ALL irrigation systems. Only use in case of actual emergency like floods, leaks, or equipment failure!",
                "confirmation_required": True,
                "examples": [
                    "Activate emergency stop",
                    "Trigger emergency shutdown",
                    "Reset emergency stop",
                    "Disable emergency mode",
                    "Engage safety shutdown"
                ],
                "navigation_instructions": "🚨 Click the red emergency button in the header or go to Control Panel → Emergency section"
            },
            "mode": {
                "description": "Switch between automatic and manual operation modes",
                "keywords": ["mode", "switch mode", "automatic", "manual", "operation mode"],
                "icon": "fa-cogs",
                "parameters": {
                    "manual": {
                        "type": "boolean",
                        "description": "True for manual mode, False for automatic mode",
                        "required": True
                    }
                },
                "examples": [
                    "Switch to manual mode",
                    "Set to automatic mode",
                    "Change to manual control",
                    "Enable automatic watering"
                ],
                "navigation_instructions": "Go to Control Panel → Settings → Operation Mode to switch between manual and automatic"
            },
            "threshold": {
                "description": "Set moisture threshold levels for automatic irrigation triggers",
                "keywords": ["threshold", "moisture level", "set threshold", "sensitivity", "moisture setting"],
                "icon": "fa-percentage",
                "parameters": {
                    "value": {
                        "type": "number",
                        "description": "Percentage value (0-100)",
                        "required": True
                    },
                    "zone": {
                        "type": "number",
                        "description": "Zone number (optional, applies to all zones if not specified)",
                        "required": False
                    }
                },
                "examples": [
                    "Set threshold to 40%",
                    "Change moisture threshold to 35",
                    "Adjust watering threshold for zone 2",
                    "Set sensitivity to 30%"
                ],
                "navigation_instructions": "Navigate to Control Panel → Settings → Thresholds to adjust moisture sensitivity levels"
            },
            "schedule": {
                "description": "Create or modify irrigation schedules for automated watering",
                "keywords": ["schedule", "timer", "plan irrigation", "watering schedule", "irrigation plan"],
                "icon": "fa-clock",
                "parameters": {
                    "time": {
                        "type": "datetime",
                        "description": "When to start irrigation",
                        "required": True
                    },
                    "duration": {
                        "type": "number",
                        "description": "Duration in minutes",
                        "required": True
                    },
                    "zones": {
                        "type": "array",
                        "description": "Array of zone numbers to irrigate",
                        "required": False
                    }
                },
                "examples": [
                    "Schedule irrigation for tomorrow at 6 AM",
                    "Create watering schedule for 30 minutes",
                    "Plan irrigation for zones 1 and 3",
                    "Set daily watering at 7 PM for 45 minutes"
                ],
                "navigation_instructions": "Go to Control Panel → Scheduling → Create New Schedule to set up automated watering"
            },
            "stop all": {
                "description": "Stop all currently active irrigation processes immediately",
                "keywords": ["stop", "halt", "cancel", "stop all", "end irrigation"],
                "icon": "fa-stop-circle",
                "parameters": {},
                "examples": [
                    "Stop all irrigation",
                    "Halt watering immediately",
                    "Cancel current irrigation",
                    "Stop all zones"
                ],
                "navigation_instructions": "Click the 'Stop All' button in the Control Panel or use the emergency stop for immediate shutdown"
            },
            "status": {
                "description": "Check current system status, sensor readings, and active operations",
                "keywords": ["status", "check", "system status", "current state", "what's running"],
                "icon": "fa-info-circle",
                "parameters": {},
                "examples": [
                    "Check system status",
                    "What is currently running?",
                    "Show current operations",
                    "Display sensor readings"
                ],
                "navigation_instructions": "View the Dashboard for an overview or go to Control Panel → Status for detailed information"
            }
        }
        return commands

    def _load_informational_pages(self):
        """Load informational content pages"""
        return {
            "water conservation": {
                "description": "Learn about water-saving techniques and efficient irrigation practices",
                "keywords": ["water", "save", "conservation", "efficient", "saving"],
                "icon": "fa-tint-slash",
                "content": "Water conservation is essential for sustainable irrigation. Key practices include:\n\n"
                           "• Using drip irrigation systems\n• Watering during early morning hours\n"
                           "• Installing rain sensors to prevent watering during rainfall\n"
                           "• Regularly checking for leaks and repairing them promptly\n"
                           "• Grouping plants with similar water needs together",
                "category": "Education",
                "importance": 7,
                "navigation_instructions": "Visit the Knowledge Base → Water Conservation section for detailed guides"
            },
            "system maintenance": {
                "description": "Guidelines for maintaining your irrigation system for optimal performance",
                "keywords": ["maintenance", "repair", "service", "checkup", "winterize"],
                "icon": "fa-tools",
                "content": "Regular maintenance ensures your irrigation system works efficiently:\n\n"
                           "• Monthly: Check for leaks and clogged sprinkler heads\n"
                           "• Quarterly: Test sensors and controllers\n"
                           "• Annually: Perform full system inspection and winterization\n"
                           "• After storms: Check for damage and clear debris",
                "category": "Maintenance",
                "importance": 6,
                "navigation_instructions": "Go to Help → Maintenance Guides for detailed maintenance schedules and procedures"
            },
            "plant watering needs": {
                "description": "Understand different watering requirements for various plant types",
                "keywords": ["plants", "watering", "needs", "vegetables", "lawn", "garden"],
                "icon": "fa-leaf",
                "content": "Different plants have different watering requirements:\n\n"
                           "• Lawns: 1-1.5 inches per week\n• Vegetables: Consistent moisture, avoid drying out\n"
                           "• Shrubs: Deep watering less frequently\n• Trees: Infrequent deep watering\n"
                           "• Container plants: More frequent watering as they dry out faster",
                "category": "Education",
                "importance": 5,
                "navigation_instructions": "Check the Plant Database in the Knowledge Base for specific watering requirements"
            }
        }

    def _load_dashboard_widgets(self):
        """Load information about dashboard widgets and their functionality"""
        return {
            "moisture levels": {
                "description": "View current soil moisture levels across all irrigation zones",
                "keywords": ["moisture", "soil", "sensor", "levels", "wetness"],
                "icon": "fa-percentage",
                "category": "Monitoring",
                "importance": 8,
                "navigation_instructions": "View the Moisture Levels widget on your Dashboard or go to Analytics → Soil Moisture"
            },
            "water usage": {
                "description": "Track water consumption over time with detailed analytics",
                "keywords": ["water", "usage", "consumption", "gallons", "liters", "meter"],
                "icon": "fa-chart-bar",
                "category": "Analytics",
                "importance": 7,
                "navigation_instructions": "Check the Water Usage widget on your Dashboard or go to Analytics → Water Consumption"
            },
            "weather forecast": {
                "description": "Integrated weather data to help plan irrigation based on conditions",
                "keywords": ["weather", "forecast", "rain", "temperature", "humidity"],
                "icon": "fa-cloud-sun",
                "category": "Planning",
                "importance": 6,
                "navigation_instructions": "View the Weather Forecast widget on your Dashboard or go to Analytics → Weather"
            },
            "system health": {
                "description": "Monitor the overall health and status of your irrigation system",
                "keywords": ["health", "status", "system", "diagnostics", "performance"],
                "icon": "fa-heartbeat",
                "category": "Monitoring",
                "importance": 9,
                "navigation_instructions": "Check the System Health widget on your Dashboard or go to Control Panel → System Status"
            }
        }

    def _load_help_resources(self):
        """Load help resources and documentation"""
        return {
            "user manual": {
                "description": "Complete user manual with detailed instructions for all features",
                "keywords": ["manual", "guide", "instructions", "documentation", "how to"],
                "icon": "fa-book",
                "url": "/help/manual",
                "category": "Documentation",
                "importance": 8,
                "navigation_instructions": "Go to Help → User Manual or click the documentation link in the footer"
            },
            "video tutorials": {
                "description": "Step-by-step video guides for common tasks and setup procedures",
                "keywords": ["video", "tutorial", "how to", "watch", "demonstration"],
                "icon": "fa-video",
                "url": "/help/videos",
                "category": "Learning",
                "importance": 7,
                "navigation_instructions": "Visit Help → Video Tutorials to watch guided demonstrations"
            },
            "faq": {
                "description": "Frequently asked questions and answers about the irrigation system",
                "keywords": ["faq", "questions", "answers", "common", "problems"],
                "icon": "fa-question-circle",
                "url": "/help/faq",
                "category": "Support",
                "importance": 6,
                "navigation_instructions": "Go to Help → FAQ for answers to common questions"
            },
            "community forum": {
                "description": "Connect with other users, share tips, and get community support",
                "keywords": ["community", "forum", "discussion", "users", "share"],
                "icon": "fa-users",
                "url": "/forum",
                "category": "Community",
                "importance": 5,
                "navigation_instructions": "Visit Community → Forum from the main menu to join discussions"
            }
        }

    def _load_chat_responses(self):
        """Load predefined chatbot responses and templates with enhanced interactions"""
        return {
            "greeting": {
                "response": "Hello! I'm your irrigation assistant. I can help you manage your system, answer questions, and troubleshoot issues. What would you like to know today?",
                "suggestions": [
                    "How do I control the pump?",
                    "What's my soil moisture?",
                    "Emergency stop info",
                    "Set up a watering schedule",
                    "Troubleshoot a problem"
                ],
                "quick_actions": [
                    {"text": "View System Status", "action": "status"},
                    {"text": "Quick Tutorial", "action": "tutorial getting started"}
                ]
            },
            "emergency_info": {
                "response": "🚨 **EMERGENCY STOP INFORMATION**\n\nThe emergency stop immediately shuts down ALL irrigation systems. This should only be used in actual emergencies such as:\n\n• Major water leaks or floods\n• Equipment malfunction\n• Safety hazards\n• Pipe bursts\n\n⚠️ **Warning**: This will stop all active irrigation immediately!",
                "follow_up": "Would you like to activate the emergency stop now?",
                "actions": [
                    {
                        "text": "🚨 Activate Emergency Stop Now",
                        "command": "emergency true",
                        "style": "danger",
                        "navigation": "Click the red emergency button in the header or go to Control Panel → Emergency section"
                    },
                    {
                        "text": "Learn More About Emergency Procedures",
                        "action": "info emergency procedures",
                        "style": "warning"
                    },
                    {
                        "text": "Contact Emergency Support",
                        "action": "contact emergency",
                        "style": "info"
                    }
                ]
            },
            "clear_chat_confirmation": {
                "response": "Are you sure you want to clear the chat history? This action cannot be undone.",
                "actions": [
                    {
                        "text": "✅ Yes, Clear Chat",
                        "action": "confirm_clear_chat",
                        "style": "danger"
                    },
                    {
                        "text": "❌ No, Keep History",
                        "action": "cancel_clear_chat",
                        "style": "secondary"
                    }
                ]
            },
            "settings_info": {
                "response": "You can customize your chat experience with these settings:",
                "options": [
                    {
                        "name": "Save Chat History",
                        "description": "Store your conversation history between sessions",
                        "default": True
                    },
                    {
                        "name": "Typing Indicators",
                        "description": "Show when the assistant is typing",
                        "default": True
                    },
                    {
                        "name": "Sound Notifications",
                        "description": "Play sounds for new messages",
                        "default": False
                    }
                ],
                "actions": [
                    {
                        "text": "Save Settings",
                        "action": "save_settings",
                        "style": "success"
                    },
                    {
                        "text": "Reset to Defaults",
                        "action": "reset_settings",
                        "style": "secondary"
                    }
                ]
            },
            "thanks": {
                "response": "You're welcome! 😊 I'm always here to help with your irrigation system. Is there anything else you'd like to know?",
                "suggestions": [
                    "How's my water usage?",
                    "Show me the control panel",
                    "Set up a schedule",
                    "Check system health"
                ]
            },
            "goodbye": {
                "response": "Goodbye! 👋 Remember, you can always come back if you need help with your irrigation system. Have a great day!",
                "quick_actions": [
                    {"text": "Quick Help", "action": "help"},
                    {"text": "System Status", "action": "status"}
                ]
            },
            "spelling_correction": {
                "response": "I noticed some possible spelling issues in your query. I've corrected it to: \"{corrected_query}\"",
                "follow_up": "Is this what you meant to ask?",
                "show_original": True
            }
        }

    def _load_tutorials(self):
        """Load interactive tutorials and step-by-step guides"""
        return {
            "getting started": {
                "title": "Getting Started with Your Irrigation System",
                "description": "Complete beginner's guide to setting up and using your irrigation system",
                "steps": [
                    {"title": "System Overview",
                     "content": "Learn about the main components of your irrigation system"},
                    {"title": "Initial Setup", "content": "Configure basic settings and preferences"},
                    {"title": "First Irrigation", "content": "Run your first watering cycle"},
                    {"title": "Monitoring", "content": "How to monitor system performance and water usage"}
                ],
                "estimated_time": "15 minutes",
                "difficulty": "Beginner",
                "icon": "fa-play-circle",
                "navigation_instructions": "Go to Tutorials → Getting Started for a step-by-step guide"
            },
            "schedule setup": {
                "title": "Creating Irrigation Schedules",
                "description": "Learn how to create and manage automated watering schedules",
                "steps": [
                    {"title": "Schedule Basics", "content": "Understanding scheduling options"},
                    {"title": "Time-based Scheduling", "content": "Set schedules based on time of day"},
                    {"title": "Sensor-based Scheduling", "content": "Use soil moisture sensors for smart watering"},
                    {"title": "Weather Integration", "content": "Incorporate weather forecasts into your schedule"}
                ],
                "estimated_time": "20 minutes",
                "difficulty": "Intermediate",
                "icon": "fa-calendar-check",
                "navigation_instructions": "Visit Tutorials → Scheduling to learn how to set up automated irrigation"
            },
            "water conservation": {
                "title": "Water Conservation Techniques",
                "description": "Optimize your irrigation for maximum water efficiency",
                "steps": [
                    {"title": "Efficient Watering", "content": "Best practices for water conservation"},
                    {"title": "Zone Optimization", "content": "Configure zones for different plant needs"},
                    {"title": "Rainwater Harvesting", "content": "Integrate rainwater collection systems"},
                    {"title": "Leak Detection", "content": "Identify and fix water leaks promptly"}
                ],
                "estimated_time": "25 minutes",
                "difficulty": "Intermediate",
                "icon": "fa-tint-slash",
                "navigation_instructions": "Check Tutorials → Water Conservation for water-saving techniques"
            }
        }

    def _load_troubleshooting_guides(self):
        """Load troubleshooting guides for common issues"""
        return {
            "pump not working": {
                "title": "Pump Not Starting",
                "description": "Troubleshoot issues with water pump not starting",
                "symptoms": ["No water flow", "Pump silent", "Error lights on pump"],
                "steps": [
                    "Check power connection to pump",
                    "Verify water supply is available",
                    "Inspect for clogged intake filters",
                    "Check circuit breakers and fuses",
                    "Review system error logs"
                ],
                "emergency": False,
                "icon": "fa-tint",
                "navigation_instructions": "Go to Troubleshooting → Pump Issues for detailed guidance"
            },
            "low water pressure": {
                "title": "Low Water Pressure",
                "description": "Address issues with low water pressure in irrigation system",
                "symptoms": ["Weak sprinkler spray", "Incomplete coverage", "Long watering times"],
                "steps": [
                    "Check main water supply pressure",
                    "Inspect for leaks in the system",
                    "Clean clogged sprinkler heads",
                    "Verify valve operation",
                    "Check for kinks in supply lines"
                ],
                "emergency": False,
                "icon": "fa-compress-arrows-alt",
                "navigation_instructions": "Visit Troubleshooting → Water Pressure for solutions"
            },
            "sensor issues": {
                "title": "Sensor Malfunctions",
                "description": "Troubleshoot problems with soil moisture sensors",
                "symptoms": ["Inaccurate readings", "Sensor offline", "Erratic behavior"],
                "steps": [
                    "Check sensor physical connections",
                    "Clean sensor probes",
                    "Verify calibration settings",
                    "Check for wireless interference",
                    "Replace batteries if wireless"
                ],
                "emergency": False,
                "icon": "fa-temperature-low",
                "navigation_instructions": "Go to Troubleshooting → Sensor Problems for help with sensor issues"
            },
            "leak detection": {
                "title": "Suspected Water Leak",
                "description": "Identify and address potential water leaks in the system",
                "symptoms": ["Unexplained water usage", "Wet areas", "Pressure drops"],
                "steps": [
                    "Conduct visual inspection of all components",
                    "Check water meter for continuous flow",
                    "Inspect valves for proper sealing",
                    "Examine connections and joints",
                    "Use leak detection dye if available"
                ],
                "emergency": True,
                "icon": "fa-faucet-drip",
                "navigation_instructions": "🚨 For suspected leaks, go to Emergency Procedures → Leak Detection immediately"
            }
        }

    def _load_contact_information(self):
        """Load contact information with enhanced details"""
        return {
            "contact": {
                "title": "Contact Information",
                "description": "Get in touch with our support team for assistance and inquiries",
                "methods": {
                    "phone": {
                        "label": "Call Us",
                        "value": "+256 780 443345",
                        "icon": "fa-phone-alt",
                        "action": "tel:+256780443345",
                        "availability": "Mon-Fri: 8:00 AM - 5:00 PM"
                    },
                    "email": {
                        "label": "Email Us",
                        "value": "nduwayomorris@gmail.com",
                        "icon": "fa-envelope",
                        "action": "mailto:nduwayomorris@gmail.com",
                        "response_time": "Within 24 hours"
                    },
                    "location": {
                        "label": "Visit Us",
                        "value": "Kyebando roundabout, Kampala City, Uganda",
                        "icon": "fa-map-marker-alt",
                        "action": "https://maps.google.com?q=Kyebando+roundabout,Kampala+City,Uganda",
                        "coordinates": "0.3499511,32.5886327"
                    }
                },
                "social_media": {
                    "facebook": {
                        "url": "https://www.facebook.com/magnus.morris.79",
                        "icon": "fab fa-facebook-f",
                        "label": "Facebook"
                    },
                    "twitter": {
                        "url": "https://x.com/NduwayoMorris",
                        "icon": "fab fa-x-twitter",
                        "label": "X (Twitter)"
                    },
                    "linkedin": {
                        "url": "https://www.linkedin.com/in/nduwayo-morris",
                        "icon": "fab fa-linkedin-in",
                        "label": "LinkedIn"
                    },
                    "whatsapp": {
                        "url": "https://wa.me/+256780443345",
                        "icon": "fab fa-whatsapp",
                        "label": "WhatsApp"
                    }
                },
                "route_info": {
                    "from": "Kyebando roundabout",
                    "to": "Bukoto Mulimira Zone",
                    "duration": "1 min (70 m)",
                    "directions": [
                        "Head northwest",
                        "Turn right",
                        "Arrive at location: Bukoto Mulimira Zone"
                    ],
                    "map_url": "https://maps.app.goo.gl/iDjPednYn7ms6G8PA?g_st=ac"
                },
                "navigation_instructions": "Scroll to the footer and click 'Contact Us' or go to Help → Contact Support"
            }
        }

    def _load_emergency_resources(self):
        """Load emergency resources and procedures with clear user instructions"""
        return {
            "emergency_procedures": {
                "title": "Emergency Procedures",
                "description": "Step-by-step instructions for handling irrigation system emergencies",
                "procedures": [
                    {
                        "title": "Major Water Leak - IMMEDIATE ACTION REQUIRED",
                        "urgency": "high",
                        "steps": [
                            "🚨 GO TO THE HEADER AND CLICK THE RED EMERGENCY BUTTON NOW",
                            "Locate main water shut-off valve and turn it off",
                            "If safe, identify the source of the leak",
                            "Contact support for assistance: +256 780 443345"
                        ],
                        "header_action": "Click the emergency stop button in the header immediately"
                    },
                    {
                        "title": "Electrical Issues",
                        "urgency": "high",
                        "steps": [
                            "Turn off power at circuit breaker",
                            "Do not touch wet equipment",
                            "Contact electrician if needed",
                            "Report issue to support team"
                        ],
                        "header_action": "Go to Control Panel → Emergency section"
                    },
                    {
                        "title": "Controller Malfunction",
                        "urgency": "medium",
                        "steps": [
                            "Reboot controller system",
                            "Check power connection",
                            "Review error logs",
                            "Contact support if issue persists"
                        ],
                        "header_action": "Go to Control Panel → System Status → Reboot System"
                    }
                ],
                "navigation_instructions": "🚨 For emergencies, use the red emergency button in the header or go to Emergency Procedures"
            }
        }

    def get_contact_response(self):
        """Generate a comprehensive contact information response"""
        contact_info = self.resources[ResourceType.CONTACT]["contact"]

        response = {
            "matched": True,
            "type": "contact",
            "title": contact_info["title"],
            "description": contact_info["description"],
            "methods": [],
            "social_media": [],
            "quick_actions": [],
            "navigation_instructions": contact_info.get("navigation_instructions", "")
        }

        # Add contact methods
        for method_key, method in contact_info["methods"].items():
            response["methods"].append({
                "type": method_key,
                "label": method["label"],
                "value": method["value"],
                "icon": method["icon"],
                "action": method["action"],
                "details": method.get("availability") or method.get("response_time", "")
            })

        # Add social media links
        for platform, info in contact_info["social_media"].items():
            response["social_media"].append({
                "platform": platform,
                "url": info["url"],
                "icon": info["icon"],
                "label": info["label"]
            })

        # Add quick actions
        response["quick_actions"] = [
            {
                "text": "📞 Call Now",
                "action": "tel:+256780443345",
                "type": "phone"
            },
            {
                "text": "✉️ Send Email",
                "action": "mailto:nduwayomorris@gmail.com",
                "type": "email"
            },
            {
                "text": "🗺️ Get Directions",
                "action": "https://maps.google.com?q=Kyebando+roundabout,Kampala+City,Uganda",
                "type": "map"
            }
        ]

        return response

    def get_emergency_contact_info(self):
        """Get emergency contact information"""
        return {
            "matched": True,
            "type": "emergency_contact",
            "title": "🚨 Emergency Support",
            "description": "Immediate assistance for critical irrigation system issues",
            "contacts": [
                {
                    "type": "urgent_phone",
                    "label": "Emergency Hotline",
                    "value": "+256 780 443345",
                    "icon": "fa-phone-alt",
                    "action": "tel:+256780443345",
                    "description": "24/7 emergency support for critical system failures"
                },
                {
                    "type": "whatsapp",
                    "label": "WhatsApp Support",
                    "value": "+256 780 443345",
                    "icon": "fab fa-whatsapp",
                    "action": "https://wa.me/+256780443345",
                    "description": "Quick messaging for urgent issues"
                },
                {
                    "type": "email",
                    "label": "Emergency Email",
                    "value": "nduwayomorris@gmail.com",
                    "icon": "fa-envelope",
                    "action": "mailto:nduwayomorris@gmail.com?subject=EMERGENCY%20-%20Irrigation%20System%20Issue",
                    "description": "For detailed emergency reports"
                }
            ],
            "quick_actions": [
                {
                    "text": "🚨 Call Emergency Line",
                    "action": "tel:+256780443345",
                    "style": "danger"
                },
                {
                    "text": "💬 WhatsApp Emergency",
                    "action": "https://wa.me/+256780443345",
                    "style": "success"
                }
            ],
            "navigation_instructions": "🚨 Use the red emergency button in the header for immediate assistance"
        }

    def _enhance_with_contact_intelligence(self, query, response):
        """Enhance responses with contact information when relevant"""
        query_lower = query.lower()

        # Check if query relates to contact or support
        contact_keywords = [
            'contact', 'support', 'help', 'call', 'email', 'phone',
            'number', 'address', 'location', 'talk to', 'speak with',
            'emergency', 'urgent', 'problem', 'issue', 'broken'
        ]

        if any(keyword in query_lower for keyword in contact_keywords):
            if 'contact_info' not in response:
                response['contact_info'] = self.get_contact_response()

            # Add emergency info if query suggests urgency
            if any(word in query_lower for word in ['emergency', 'urgent', 'critical', 'broken', 'not working']):
                response['emergency_info'] = self.get_emergency_contact_info()

        return response

    def _get_command_examples(self, command_name):
        """Generate usage examples for commands"""
        examples = {
            "pump": [
                "Turn on the pump",
                "Activate water pump",
                "Stop the pump",
                "Set pump to ON",
                "Start main water pump now"
            ],
            "valve": [
                "Open valve for zone 1",
                "Close irrigation valve 3",
                "Turn on zone 2 valve",
                "Activate valve in area 4",
                "Shut off zone 5"
            ],
            "emergency": [
                "Activate emergency stop",
                "Trigger emergency shutdown",
                "Reset emergency stop",
                "Disable emergency mode",
                "Engage safety shutdown"
            ],
            "mode": [
                "Switch to manual mode",
                "Set to automatic mode",
                "Change to manual control",
                "Enable automatic watering",
                "Go back to auto mode"
            ],
            "threshold": [
                "Set threshold to 40%",
                "Change moisture threshold to 35",
                "Adjust watering threshold for zone 2",
                "Set sensitivity to 30%",
                "Make threshold 25 percent"
            ],
            "schedule": [
                "Schedule irrigation for tomorrow at 6 AM",
                "Create watering schedule for 30 minutes",
                "Plan irrigation for zones 1 and 3",
                "Set daily watering at 7 PM for 45 minutes",
                "Make a schedule for morning watering"
            ]
        }
        return examples.get(command_name, [])

    def update_user_context(self, user_id, key, value):
        """Update context for a specific user"""
        if user_id not in self.user_context:
            self.user_context[user_id] = {}
        self.user_context[user_id][key] = value

    def get_user_context(self, user_id):
        """Get context for a specific user"""
        return self.user_context.get(user_id, {})

    def update_user_preferences(self, user_id, preferences):
        """Update user preferences for personalized responses"""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {}
        self.user_preferences[user_id].update(preferences)

    def get_user_preferences(self, user_id):
        """Get preferences for a specific user"""
        return self.user_preferences.get(user_id, {})

    def add_to_conversation_history(self, user_id, query, response):
        """Add interaction to conversation history"""
        timestamp = datetime.now().isoformat()
        interaction = {
            "timestamp": timestamp,
            "query": query,
            "response": response[:500]  # Limit response length
        }

        if user_id not in self.conversation_history:
            self.conversation_history[user_id] = []

        self.conversation_history[user_id].append(interaction)
        # Keep only last 20 interactions
        if len(self.conversation_history[user_id]) > 20:
            self.conversation_history[user_id] = self.conversation_history[user_id][-20:]

    def get_conversation_context(self, user_id, max_interactions=5):
        """Get recent conversation context for better responses"""
        if user_id not in self.conversation_history:
            return ""

        recent = self.conversation_history[user_id][-max_interactions:]
        context = "Recent conversation history:\n"
        for i, interaction in enumerate(recent):
            context += f"{i + 1}. User: {interaction['query']}\n   Bot: {interaction['response']}\n"

        return context

    def find_best_match(self, query, user_id=None):
        """Find the most relevant resource for a user query with enhanced matching"""
        query = query.lower().strip()

        # Get conversation context for better matching
        conversation_context = self.get_conversation_context(user_id) if user_id else ""

        # First check for exact matches in all resource types
        for resource_type in ResourceType:
            for name, data in self.resources[resource_type].items():
                if query == name.lower():
                    return name, resource_type

                # Check if query matches any keyword exactly
                if any(query == kw.lower() for kw in data.get("keywords", [])):
                    return name, resource_type

        # Then check for partial matches in keywords with context awareness
        for resource_type in ResourceType:
            for name, data in self.resources[resource_type].items():
                # Check if any keyword appears in query
                if any(kw in query for kw in data.get("keywords", [])):
                    return name, resource_type

                # Check if query contains words from description (context-aware)
                description_words = set(data.get("description", "").lower().split())
                query_words = set(query.split())
                if len(description_words & query_words) >= 2:  # At least 2 matching words
                    return name, resource_type

        # Use fuzzy matching as fallback with context consideration
        all_names = []
        for resource_type in ResourceType:
            all_names.extend(self.resources[resource_type].keys())

        matches = get_close_matches(query, all_names, n=3, cutoff=0.5)
        if matches:
            # Prioritize matches that fit conversation context
            for match in matches:
                for resource_type in ResourceType:
                    if match in self.resources[resource_type]:
                        return match, resource_type

        return None, None

    def get_help_response(self, query, request=None, user_id=None):
        """Generate a complete help response for a user query with JSON intent matching"""
        try:
            if user_id:
                self.add_to_conversation_history(user_id, query, "Processing...")

            # First try to match against JSON intents
            json_response = self.json_loader.get_response(query)
            if json_response['matched'] and json_response['confidence'] >= 0.6:
                if user_id:
                    self.add_to_conversation_history(user_id, query, json_response['response'])

                response = {
                    "matched": True,
                    "type": "json_intent",
                    "query": query,
                    "response": json_response['response'],
                    "intent": json_response['intent'],
                    "category": json_response['category'],
                    "confidence": json_response['confidence'],
                    "response_type": "success",
                    "suggestions": json_response['suggestions']
                }
                return response

            # Check for special commands first
            special_response = self._check_special_commands(query)
            if special_response:
                if user_id:
                    self.add_to_conversation_history(user_id, query,
                                                     special_response.get("response", "Special command executed"))
                return special_response

            # Check for spelling errors and correct them
            corrected_query, corrections = self.spelling_corrector.correct_spelling(query)
            has_spelling_issues = corrected_query.lower() != query.lower()

            # Check for conversational phrases
            conversational_response = self._check_conversational_phrases(corrected_query)
            if conversational_response:
                if user_id:
                    self.add_to_conversation_history(user_id, query, conversational_response["response"])
                return conversational_response

            # Check for contact-related queries
            contact_keywords = ['contact', 'support', 'help', 'call', 'email', 'phone', 'emergency']
            if any(keyword in corrected_query.lower() for keyword in contact_keywords):
                if 'emergency' in corrected_query.lower():
                    response = self.get_emergency_contact_info()
                else:
                    response = self.get_contact_response()

                if user_id:
                    self.add_to_conversation_history(user_id, query, "Provided contact information")

                if has_spelling_issues:
                    response['spelling_correction'] = {
                        'original_query': query,
                        'corrected_query': corrected_query,
                        'corrections': corrections
                    }
                return response

            # Fall back to original resource matching if no JSON intent matched
            resource_name, resource_type = self.find_best_match(corrected_query, user_id)
            if not resource_name:
                response = {
                    "matched": False,
                    "message": "I couldn't find an exact match for your query. Try being more specific or ask about:",
                    "suggestions": self.get_suggestions(corrected_query),
                    "response_type": "error"
                }
                if has_spelling_issues:
                    response['spelling_correction'] = {
                        'original_query': query,
                        'corrected_query': corrected_query,
                        'corrections': corrections
                    }
                return response

            # Process resource-based response
            resource_data = self.resources[resource_type][resource_name]
            response = {
                "matched": True,
                "type": resource_type.value,
                "query": query,
                "corrected_query": corrected_query if has_spelling_issues else None,
                "resource": {
                    "name": resource_name,
                    "description": resource_data["description"],
                    "icon": resource_data.get("icon", "fa-question-circle"),
                    "navigation_instructions": resource_data.get("navigation_instructions", "")
                },
                "suggestions": self.get_suggestions(corrected_query),
                "response_type": "success"
            }

            if has_spelling_issues:
                response['spelling_correction'] = {
                    'original_query': query,
                    'corrected_query': corrected_query,
                    'corrections': corrections
                }

            # Add type-specific details
            if resource_type == ResourceType.ROUTE:
                try:
                    response["resource"]["url"] = str(resource_data["url"])
                except:
                    response["resource"]["url"] = "/"
                response["resource"]["category"] = resource_data.get("category", "")
                response["resource"]["importance"] = resource_data.get("importance", 5)

            elif resource_type == ResourceType.COMMAND:
                response["resource"]["examples"] = resource_data.get("examples", [])
                if "safety_warning" in resource_data:
                    response["resource"]["safety_warning"] = resource_data["safety_warning"]
                if "safety_note" in resource_data:
                    response["resource"]["safety_note"] = resource_data["safety_note"]

            # Enhance with contact information when relevant
            response = self._enhance_with_contact_intelligence(corrected_query, response)

            if user_id:
                self.add_to_conversation_history(user_id, query, f"Found resource: {resource_name}")

            return response

        except Exception as e:
            logger.error(f"Error in get_help_response: {str(e)}")
            return {
                "matched": False,
                "message": "I encountered an error processing your request. Please try again or contact support if the issue persists.",
                "suggestions": [],
                "response_type": "error"
            }

    def _check_special_commands(self, query):
        """Check for special commands like clear chat, settings, etc."""
        query_lower = query.lower()

        if any(cmd in query_lower for cmd in ["clear chat", "delete history", "reset conversation"]):
            return self._format_chat_response("clear_chat_confirmation")

        elif any(cmd in query_lower for cmd in ["settings", "preferences", "options"]):
            return self._format_chat_response("settings_info")

        elif any(cmd in query_lower for cmd in ["emergency", "urgent", "help now"]):
            return self._format_chat_response("emergency_info")

        return None

    def _check_conversational_phrases(self, query):
        """Check for common conversational phrases and provide appropriate responses"""
        query_lower = query.lower()

        # Greetings
        if any(word in query_lower for word in ["hello", "hi", "hey", "greetings", "good morning", "good afternoon"]):
            return self._format_chat_response("greeting")

        # Thanks
        if any(word in query_lower for word in ["thank", "thanks", "appreciate", "grateful"]):
            return self._format_chat_response("thanks")

        # Goodbye
        if any(word in query_lower for word in ["bye", "goodbye", "see you", "farewell"]):
            return self._format_chat_response("goodbye")

        return None

    def execute_special_command(self, command, user_id=None):
        """Execute special commands like clearing chat, changing settings, etc."""
        if command == "confirm_clear_chat":
            if user_id and user_id in self.conversation_history:
                self.conversation_history[user_id] = []
            return {
                "matched": True,
                "type": "system",
                "response": "Chat history has been cleared successfully.",
                "response_type": "success"
            }

        elif command == "save_settings":
            return {
                "matched": True,
                "type": "system",
                "response": "Your settings have been saved successfully.",
                "response_type": "success"
            }

        return None

    def _get_contextual_help(self, recent_topics, current_topic):
        """Provide contextual help based on recent conversation topics"""
        contextual_help = []

        # Analyze recent topics for patterns
        topics_text = " ".join(recent_topics).lower()

        if any(word in topics_text for word in ["how", "setup", "configure", "install"]):
            contextual_help.append({
                "type": "tutorial",
                "message": "Based on your recent questions, you might find our setup tutorials helpful:",
                "suggestions": ["getting started", "schedule setup", "zone configuration"]
            })

        if any(word in topics_text for word in ["problem", "issue", "error", "not working"]):
            contextual_help.append({
                "type": "troubleshooting",
                "message": "It seems you're experiencing some issues. Check our troubleshooting guides:",
                "suggestions": ["pump not working", "low water pressure", "sensor issues"]
            })

        if any(word in topics_text for word in ["water", "save", "conservation", "efficient"]):
            contextual_help.append({
                "type": "tips",
                "message": "Interested in water conservation? Here are some resources:",
                "suggestions": ["water conservation", "efficient scheduling", "zone optimization"]
            })

        return contextual_help

    def _format_chat_response(self, response_key):
        """Format a predefined chatbot response with enhanced features"""
        try:
            chat_data = self.resources[ResourceType.CHAT].get(response_key, {})
            response = {
                "matched": True,
                "type": "chat",
                "response": chat_data.get("response", ""),
                "response_type": "chat"
            }

            if "suggestions" in chat_data:
                response["suggestions"] = [
                    {"name": s, "type": "suggestion"}
                    for s in chat_data["suggestions"]
                ]

            if "actions" in chat_data:
                response["actions"] = chat_data["actions"]

            if "categories" in chat_data:
                response["categories"] = chat_data["categories"]

            if "quick_actions" in chat_data:
                response["quick_actions"] = chat_data["quick_actions"]

            return response
        except Exception as e:
            logger.error(f"Error in _format_chat_response: {str(e)}")
            return {
                "matched": False,
                "message": "I encountered an error processing your request.",
                "suggestions": [],
                "response_type": "error"
            }

    def get_suggestions(self, query, limit=5):
        """Get related resource suggestions based on query with intelligent scoring"""
        try:
            query_words = set(query.lower().split())
            suggestions = []

            for resource_type in ResourceType:
                for name, data in self.resources[resource_type].items():
                    if resource_type == ResourceType.CHAT:
                        continue

                    # Calculate relevance score
                    score = 0

                    # Keyword matches
                    name_words = set(name.lower().split())
                    keyword_words = set(kw.lower() for kw in data.get("keywords", []))

                    # Exact matches
                    score += 3 * len(query_words & name_words)
                    score += 2 * len(query_words & keyword_words)

                    # Partial matches
                    for q_word in query_words:
                        for k_word in keyword_words:
                            if q_word in k_word or k_word in q_word:
                                score += 1

                    # Description relevance
                    description_words = set(data.get("description", "").lower().split())
                    score += len(query_words & description_words) * 0.5

                    # Importance factor
                    score += data.get("importance", 5) * 0.1

                    if score > 0:
                        suggestion = {
                            "name": name,
                            "score": score,
                            "icon": data.get("icon", "fa-link"),
                            "type": resource_type.value,
                            "category": data.get("category", ""),
                            "description": data.get("description", "")[:100] + "..." if len(
                                data.get("description", "")) > 100 else data.get("description", "")
                        }
                        if resource_type == ResourceType.ROUTE:
                            try:
                                suggestion["url"] = str(data["url"])
                            except:
                                suggestion["url"] = "/"
                        suggestions.append(suggestion)

            # Return top suggestions by score, with diversity (not all from same category)
            suggestions.sort(key=lambda x: x["score"], reverse=True)

            # Ensure diversity in results
            final_suggestions = []
            categories_used = set()

            for suggestion in suggestions:
                if len(final_suggestions) >= limit:
                    break
                if suggestion["category"] not in categories_used or len(categories_used) >= 3:
                    final_suggestions.append(suggestion)
                    categories_used.add(suggestion["category"])

            return final_suggestions[:limit]
        except Exception as e:
            logger.error(f"Error in get_suggestions: {str(e)}")
            return []

    def get_all_resources(self, category_filter=None):
        """Get all available resources across all categories with optional filtering"""
        resources = []

        for resource_type in ResourceType:
            # Skip chatbot responses for the resource listing
            if resource_type == ResourceType.CHAT:
                continue

            for name, data in self.resources[resource_type].items():
                # Apply category filter if provided
                if category_filter and data.get("category") != category_filter:
                    continue

                resource = {
                    "name": name,
                    "description": data["description"],
                    "icon": data.get("icon", "fa-question-circle"),
                    "type": resource_type.value,
                    "category": data.get("category", ""),
                    "importance": data.get("importance", 5)
                }
                if resource_type == ResourceType.ROUTE:
                    try:
                        resource["url"] = str(data["url"])
                    except:
                        resource["url"] = "/"
                resources.append(resource)

        # Sort by importance then alphabetically
        resources.sort(key=lambda x: (-x["importance"], x["name"]))
        return resources

    def get_learning_path(self, user_level="beginner"):
        """Generate a learning path based on user experience level"""
        paths = {
            "beginner": [
                "getting started",
                "pump",
                "valve",
                "status",
                "dashboard"
            ],
            "intermediate": [
                "schedule",
                "threshold",
                "zones",
                "analytics",
                "water conservation"
            ],
            "advanced": [
                "mode",
                "emergency",
                "troubleshooting",
                "download data",
                "scheduling"
            ]
        }

        return paths.get(user_level, paths["beginner"])

    def get_daily_tip(self):
        """Get a daily tip for irrigation system optimization"""
        tips = [
            "💧 Check your soil moisture sensors regularly for accurate readings.",
            "🌦️ Adjust watering schedules based on seasonal weather changes.",
            "🔧 Perform monthly maintenance checks on valves and sprinklers.",
            "📊 Review water usage reports weekly to identify conservation opportunities.",
            "🌱 Group plants with similar water needs in the same irrigation zones.",
            "⏰ Water early in the morning to reduce evaporation loss.",
            "🚰 Check for leaks monthly - a small leak can waste hundreds of gallons.",
            "🌧️ Install a rain sensor to avoid watering during rainfall.",
            "📱 Use the mobile app to monitor your system remotely.",
            "🔍 Regularly inspect sprinkler heads for proper alignment and coverage."
        ]

        # Use date-based selection for consistent daily tips
        day_of_year = datetime.now().timetuple().tm_yday
        return tips[day_of_year % len(tips)]

    def analyze_conversation_patterns(self, user_id):
        """Analyze conversation patterns to provide personalized recommendations"""
        if user_id not in self.conversation_history:
            return None

        conversations = self.conversation_history[user_id]
        if len(conversations) < 3:
            return None

        # Analyze topics and patterns
        topics = []
        for conv in conversations[-5:]:  # Last 5 conversations
            query = conv["query"].lower()

            # Categorize queries
            if any(word in query for word in ["pump", "valve", "control"]):
                topics.append("control")
            elif any(word in query for word in ["schedule", "timer", "automatic"]):
                topics.append("scheduling")
            elif any(word in query for word in ["problem", "issue", "error", "not working"]):
                topics.append("troubleshooting")
            elif any(word in query for word in ["water", "save", "conservation"]):
                topics.append("conservation")
            elif any(word in query for word in ["dashboard", "status", "monitor"]):
                topics.append("monitoring")

        # Find most common topic
        if topics:
            from collections import Counter
            topic_counts = Counter(topics)
            most_common = topic_counts.most_common(1)[0][0]

            recommendations = {
                "control": ["Learn advanced valve control", "Pump maintenance guide"],
                "scheduling": ["Weather-based scheduling", "Zone-specific schedules"],
                "troubleshooting": ["Common issue solutions", "Preventative maintenance"],
                "conservation": ["Water saving techniques", "Rainwater harvesting"],
                "monitoring": ["Advanced analytics", "Custom dashboard widgets"]
            }

            return {
                "interest_area": most_common,
                "recommendations": recommendations.get(most_common, [])
            }

        return None
