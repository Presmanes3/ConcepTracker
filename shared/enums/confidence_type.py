from enum import Enum

class ConfidenceType(str, Enum):
    IDEA = "idea"
    FACT = "fact"
    HYPOTHESIS = "hypothesis"