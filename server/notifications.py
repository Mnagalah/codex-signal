"""Ephemeral metadata-only task edges; never writes a conversation or history."""
import copy
import time
import uuid

if __package__:
    from .localization import text
else:
    from localization import text


class NoticeTracker:
    PHASES = {'running', 'approval', 'input', 'completed', 'failed', 'stopped'}

    def __init__(self):
        self.phases = {}
        self.visible = {}

    def seed(self, entries):
        self.phases = {key: entry['phase'] for key, entry in entries.items() if entry.get('phase') in self.PHASES}

    def reset(self):
        self.phases.clear()
        self.visible.clear()

    def forget(self, keys):
        for key in keys:
            self.phases.pop(key, None)
            self.visible.pop(key, None)

    def observe(self, states, groups, connected, language, identities=None, allowed_phases=None):
        current = {}
        for project in groups:
            identity = {key: value for key, value in project.items() if key != 'threads'}
            identity['threads'] = []
            for chat in project['threads']:
                current[chat['id']] = {'project': identity, 'chat': chat}
        result = None
        allowed = self.PHASES if allowed_phases is None else allowed_phases
        excluded = {key for key, state in states.items()
                    if state.metadata.get('ephemeral') or state.metadata.get('parentThreadId')}
        self.forget(excluded)
        if connected:
            for key, state in states.items():
                if not state.valid or state.metadata.get('ephemeral') or state.metadata.get('parentThreadId'):
                    continue
                phase = state.phase()
                if phase == 'unknown':
                    continue  # A transport/revision gap is not a task transition.
                previous = self.phases.get(key)
                self.phases[key] = phase
                subject = current.get(key) or self.visible.get(key)
                if previous is None or previous == phase or phase not in allowed or subject is None:
                    continue  # First snapshot establishes a baseline, not a replay.
                result = copy.deepcopy(subject)
                if identities and key in identities:
                    result['project'] = {**identities[key], 'threads': []}
                if state.metadata.get('title'):
                    result['chat']['title'] = state.metadata['title']
                result['chat'].update(status=phase, detail=text("noticeCompleted" if phase == "completed" else phase, language))
                result.update(id=uuid.uuid4().hex, source='automatic', createdAt=time.time())
        # A runtime may publish idle before the final turn arrives. Retain the
        # last visible subject through that gap, including already-viewed ends.
        self.visible = {key: value for key, value in self.visible.items() if key in states}
        self.visible.update(copy.deepcopy({key: value for key, value in current.items() if key not in excluded}))
        return result  # One card: the latest edge replaces earlier concurrent ones.
