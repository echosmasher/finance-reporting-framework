# Data Dictionary — Test Fixture

Same conventions as `examples/example-hotels/config/data-dictionary.md`.
`validate_data.py`/`preprocess.py` read the fenced block below, same as
the real demo config — this file became load-bearing once
`load_data_conventions()` started requiring every config to have one.

```yaml
conventions:
  delimiter: ","
  decimal_separator: "."
  thousands_separator: ""
  encoding: "utf-8"
  date_format: "%Y-%m-%d"
  sign_convention: "all_positive"
```
