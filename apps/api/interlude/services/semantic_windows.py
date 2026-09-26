"""Bounded independent inference, consumed chronologically for safe context memory."""
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

from interlude.domain import Phase2Semantics
from interlude.providers.base import ProviderError
from interlude.services.media import MediaError, extract_window


def ordered_windows(events, concurrency, analyze):
    """At most concurrency windows in flight; ordering never depends on model latency."""
    with ThreadPoolExecutor(max_workers=concurrency,thread_name_prefix='semantic-window') as executor:
        iterator=iter(enumerate(events))
        pending=deque()
        for _ in range(concurrency):
            item=next(iterator,None)
            if item is not None:
                pending.append((item,executor.submit(analyze,*item)))
        while pending:
            (index,timestamp),future=pending.popleft()
            yield index,timestamp,future.result()
            item=next(iterator,None)
            if item is not None:
                pending.append((item,executor.submit(analyze,*item)))


def perceive_window(settings,source,duration,work,perception,transcript,vocabulary,video_hash,catalogue_hash,
                    boundaries,index,timestamp):
    started=time.perf_counter()
    frames=[]
    nearby=transcript.around(timestamp-5,timestamp+5)
    try:
        frames=extract_window(settings,source,timestamp,duration,work/f'window_{index}')
        semantic=perception.perceive(frames,nearby,vocabulary,timestamp,video_hash,catalogue_hash,
                                     'boundary' if timestamp in boundaries else 'context_monitor')
        if not isinstance(semantic,Phase2Semantics):
            raise ProviderError('semantic_invalid_contract')
        return frames,nearby,semantic,None,time.perf_counter()-started
    except (ProviderError,MediaError) as exc:
        code=exc.code if isinstance(exc,ProviderError) else 'semantic_frame_window_failed'
        return frames,nearby,None,code,time.perf_counter()-started
