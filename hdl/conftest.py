def pytest_addoption(parser):
    try:
        parser.addoption("--waves", action="store_true",
                         help="Enable VCD waves (+trace; writes build/waves.vcd)")
    except ValueError:
        pass
    parser.addoption("--tc", help="Exact cocotb test name to run (optional)")
