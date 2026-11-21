# Rolling mean

The **exponential** moving average smooths a `signal` over time.

## Usage

- Set `decay` between `0` and `1`.
- See [the docs](https://example.com) for details.

```python
acc = decay * acc + (1 - decay) * x
```
