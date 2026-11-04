from esham.news_queue import NewsQueue


def test_news_queue_fair_share_round_robin():
    q = NewsQueue(per_category_max=10)

    # Enqueue multiple items for BIST and single items for others
    for i in range(5):
        q.enqueue(f"bist_{i}", "bist")
    q.enqueue("kripto_0", "kripto")
    q.enqueue("global_0", "global")
    q.enqueue("gundem_0", "gundem")
    q.enqueue("teknoloji_0", "teknoloji")

    assert len(q) == 9

    # Dequeueing should rotate across available regular categories (kripto, global, gundem, teknoloji, bist)
    dequeued = []
    for _ in range(5):
        item = q.dequeue()
        assert item is not None
        dequeued.append(item)

    # First round must include 1 item from each of the 5 categories!
    categories_hit = {item.split("_")[0] for item in dequeued}
    assert categories_hit == {"bist", "kripto", "global", "gundem", "teknoloji"}

    # Next items should drain remaining BIST items
    remaining = []
    while True:
        item = q.dequeue()
        if item is None:
            break
        remaining.append(item)

    assert len(remaining) == 4
    assert all(item.startswith("bist_") for item in remaining)
    assert len(q) == 0


def test_news_queue_ipo_priority():
    q = NewsQueue(per_category_max=10)

    q.enqueue("bist_0", "bist")
    q.enqueue("kripto_0", "kripto")
    q.enqueue("ipo_urgent", "ipo")

    # IPO must come out first
    assert q.dequeue() == "ipo_urgent"
    # Then round robin for regular
    next_item = q.dequeue()
    assert next_item in ("bist_0", "kripto_0")


def test_news_queue_per_category_limit():
    q = NewsQueue(per_category_max=3)

    # Flood BIST with 10 items
    for i in range(10):
        q.enqueue(f"bist_{i}", "bist")

    # Add 1 crypto item
    q.enqueue("kripto_0", "kripto")

    # BIST should only have 3 items (the newest: 7, 8, 9)
    # Crypto item must NOT be evicted!
    assert len(q) == 4
    stats = q.stats()
    assert stats["bist"] == 3
    assert stats["kripto"] == 1
