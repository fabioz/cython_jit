class CythonGenerator(object):

    def __init__(self):
        self.lines = []

    def generate(self, collector):
        def_line = collector.func_lines[0].strip()
        assert def_line.endswith(':'), \
            'Can currently only support function where def starts and ends in same line. Found: %s' % (def_line,)
        assert def_line.startswith('def '), \
            'Expected line: %s to start with def.' % (def_line,)

        collector.get_def_line()

        self.lines.append(collector.get_def_line())
        self.lines.extend(collector.func_lines[1:])
