def test_parse_tasks_by_name():
    task_dict = {
        "Write": 5,
        "Read": 3,
        "Workout": 4,
        "Meditate": 2,
        "Code": 6,
    }
    
    # Test valid tasks
    raw_tasks = "Write\nRead\nWorkout"
    tasks, score = parse_tasks_by_name(raw_tasks, task_dict)
    assert score == 12  # 5 + 3 + 4
    assert len(tasks) == 3

    # Test task with overridden points
    raw_tasks = "Write=7\nRead\nWorkout"
    tasks, score = parse_tasks_by_name(raw_tasks, task_dict)
    assert score == 14  # 7 + 3 + 4
    assert len(tasks) == 3

    # Test invalid task
    raw_tasks = "Write\nInvalidTask\nWorkout"
    tasks, score = parse_tasks_by_name(raw_tasks, task_dict)
    assert score == 9  # 5 + 4
    assert len(tasks) == 2

    # Test empty input
    raw_tasks = ""
    tasks, score = parse_tasks_by_name(raw_tasks, task_dict)
    assert score == 0
    assert len(tasks) == 0

def test_get_yesterday_score(mocker):
    mocker.patch('app.get_yesterday_score', return_value=10)
    assert get_yesterday_score() == 10

def test_save_today(mocker):
    mocker.patch('app.c.execute')
    save_today('2023-10-01', [('Write', 5)], 5, 0.0, False)
    app.c.execute.assert_called_once_with(
        "REPLACE INTO scores (date, tasks, score, delta_pct, improved) VALUES (?, ?, ?, ?, ?)",
        ('2023-10-01', 'Write=5', 5, 0.0, 0)
    )