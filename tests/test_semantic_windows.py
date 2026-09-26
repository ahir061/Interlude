from threading import Event
from interlude.services.semantic_windows import ordered_windows


def test_parallel_perception_is_consumed_in_story_order():
    second_started=Event()
    def analyze(index,timestamp):
        if index==0:
            assert second_started.wait(2)
        if index==1:
            second_started.set()
        return timestamp
    result=list(ordered_windows([5,10,15,20],2,analyze))
    assert result==[(0,5,5),(1,10,10),(2,15,15),(3,20,20)]
