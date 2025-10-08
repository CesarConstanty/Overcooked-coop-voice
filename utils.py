#!/usr/bin/env python3
"""
Utilities pour l'application Overcooked
"""

import threading
import json


class ThreadSafeDict(dict):
    """
    Dictionnaire thread-safe pour les opérations concurrentes
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.RLock()
    
    def __getitem__(self, key):
        with self._lock:
            return super().__getitem__(key)
    
    def __setitem__(self, key, value):
        with self._lock:
            super().__setitem__(key, value)
    
    def __delitem__(self, key):
        with self._lock:
            super().__delitem__(key)
    
    def __contains__(self, key):
        with self._lock:
            return super().__contains__(key)
    
    def get(self, key, default=None):
        with self._lock:
            return super().get(key, default)
    
    def pop(self, key, default=None):
        with self._lock:
            return super().pop(key, default)
    
    def keys(self):
        with self._lock:
            return list(super().keys())
    
    def values(self):
        with self._lock:
            return list(super().values())
    
    def items(self):
        with self._lock:
            return list(super().items())


class ThreadSafeSet(set):
    """
    Set thread-safe pour les opérations concurrentes
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.RLock()
    
    def add(self, item):
        with self._lock:
            super().add(item)
    
    def remove(self, item):
        with self._lock:
            super().remove(item)
    
    def discard(self, item):
        with self._lock:
            super().discard(item)
    
    def __contains__(self, item):
        with self._lock:
            return super().__contains__(item)
    
    def __len__(self):
        with self._lock:
            return super().__len__()
    
    def pop(self):
        with self._lock:
            return super().pop()
    
    def clear(self):
        with self._lock:
            super().clear()


def questionnaire_to_surveyjs(questionnaire_data):
    """
    Convertit les données de questionnaire au format SurveyJS
    """
    if isinstance(questionnaire_data, str):
        try:
            questionnaire_data = json.loads(questionnaire_data)
        except json.JSONDecodeError:
            return questionnaire_data
    
    # Si c'est déjà au bon format, retourne tel quel
    if isinstance(questionnaire_data, dict):
        return questionnaire_data
    
    # Sinon retourne tel quel
    return questionnaire_data
