## Summary

<!-- What does this PR do? One paragraph. -->

## Type of change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] New ERP integration
- [ ] Documentation update

## Checklist

- [ ] I have run `uv run ruff check . && uv run ruff format --check .`
- [ ] I have run `uv run mypy src/ --strict` with zero errors
- [ ] I have run `uv run pytest tests/ --cov=src/ --cov-fail-under=80` and all tests pass
- [ ] I have added tests for any new behavior
- [ ] I have added a CHANGELOG entry for any user-facing change
- [ ] If this is an AI-assisted PR, I have reviewed and validated every line of generated code
- [ ] If this changes performance-sensitive code, I have included benchmark output below

## Benchmark output (if applicable)

```
python benchmarks/run.py
```

## Related issues

Closes #
