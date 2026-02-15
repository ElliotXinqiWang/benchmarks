---
name: verify-before-submit
triggers:
  - /verify-before-submit
  - verify before submit
  - pre-submission verification
description: Pre-submission verification checklist for ensuring patch quality before calling finish
---

# Pre-submission Verification Checklist

You have invoked the pre-submission verification skill. Before calling `finish`, you MUST:

1. Complete all applicable verification checks from the list below
2. Document your verification results in your think action
3. Only proceed to `finish` if ALL applicable checks PASS

---

## ✓ CHECK 1: I/O Round-trip Testing

**Applies if your patch modifies:**
- File read/write operations
- Serialization/deserialization (pickle, JSON, etc.)
- Format/parse functions (e.g., formatting output then parsing it back)
- Data encoding/decoding

**THEN you MUST verify round-trip consistency:**

```python
# Pattern 1: write → read consistency
original_data = create_test_data()
write_function(original_data, "/tmp/test_file")
read_back = read_function("/tmp/test_file")
assert read_back == original_data, f"Write-read mismatch: {original_data} vs {read_back}"

# Pattern 2: format → parse consistency
original_obj = create_test_object()
formatted_str = format_function(original_obj)
parsed_obj = parse_function(formatted_str)
assert parsed_obj == original_obj, f"Format-parse mismatch: {original_obj} vs {parsed_obj}"
```

**CRITICAL POINTS:**
- If you modified **write logic**, you MUST also test that **read logic** correctly reads it back
- If you modified **format logic**, you MUST test that **parse logic** correctly parses it
- Testing only one direction (write OR read) is **INSUFFICIENT**

**Example:** If you fixed a bug in table.write(), you MUST verify table.read() works with the new format.

---

## ✓ CHECK 2: Differential Testing (for numerical/computational code)

**Applies if your patch modifies:**
- Mathematical calculations
- Numerical algorithms
- Data transformations
- Scientific computations

**THEN you MUST verify against a reference implementation:**

```python
import numpy as np  # or other standard library

# Test against reference implementation
test_inputs = [input1, input2, input3, ...]
for inp in test_inputs:
    your_result = your_modified_function(inp)
    reference = numpy_equivalent(inp)  # or previous version baseline

    np.testing.assert_allclose(
        your_result, reference,
        rtol=1e-10,
        err_msg=f"Mismatch for {inp}: {your_result} vs {reference}"
    )
```

**If no reference implementation exists, at minimum verify:**
- Hand-calculated expected outputs for known inputs
- Mathematical properties (e.g., idempotency: f(f(x)) == f(x))
- Known invariants (e.g., sum of probabilities = 1.0)

---

## ✓ CHECK 3: Operator Precedence and Expression Correctness

**Applies if your patch modifies:**
- Operator overloading (`__add__`, `__sub__`, `__or__`, `__and__`, etc.)
- Expression evaluation
- Set/bitwise/arithmetic operations
- Regular expressions or parser logic

**THEN you MUST verify operator precedence is correct:**

```python
# Example: (A - B) | C  vs  A - (B | C) give DIFFERENT results!

# Create test cases where precedence matters
A = {1, 2, 3, 4}
B = {2, 3}
C = {3, 4, 5}

# If you meant (A - B) | C:
expected = {1, 4} | {3, 4, 5}  # = {1, 3, 4, 5}

# Make sure your code doesn't accidentally do A - (B | C)
wrong = {1, 2, 3, 4} - ({2, 3} | {3, 4, 5})  # Different result!

result = your_expression_with_A_B_C()
assert result == expected, f"Operator precedence error: {result} != {expected}"
```

**KEY:** Don't just test with the issue's minimal example. Create test cases with **non-empty intersections/overlaps** to trigger precedence bugs.

---

## ✓ CHECK 4: Boundary and Special Value Testing

For each input parameter your code handles, test these boundary values:

| Parameter Type | Required Boundary Values |
|---------------|-------------------------|
| Strings | `""` (empty), `" "` (whitespace), very long strings, Unicode |
| Numbers | `0`, `-1`, negative values, `NaN`, `Infinity`, very large/small |
| Collections | `[]` (empty), single element, all same elements, overlapping sets |
| Paths | `"path"`, `"./path"`, `"../x/path"`, absolute paths, paths with spaces |
| Objects | `None`, subclass instances, mock objects |
| Datetime | timezone-aware, timezone-naive, different timezones |

---

## ✓ CHECK 5: Regression Testing (Run Existing Tests)

**CRITICAL: Before submitting, run the existing test suite for modules you modified.**

Recommended workflow:
```bash
# 1. Before modifying code, record baseline (if possible)
python -m pytest tests/relevant_module/ -v --tb=no > /tmp/baseline.txt 2>&1

# 2. Apply your modifications

# 3. Reinstall to ensure changes are reflected
cd {{ instance.repo_path }} && pip install -e . --no-deps

# 4. Run the same tests again
python -m pytest tests/relevant_module/ -v --tb=short > /tmp/modified.txt 2>&1

# 5. Check for regressions
diff <(grep "PASSED" /tmp/baseline.txt | sort) \
     <(grep "PASSED" /tmp/modified.txt | sort)
```

**If any previously-passing test now fails, you MUST fix the regression before submitting.**

For large-scale refactoring (>50 lines or >3 files changed):
- Run at least two related test modules
- Run all tests for any classes where you modified `__eq__`, `__hash__`, `__repr__`, or other fundamental methods

---

## ✓ CHECK 6: Semantic Correctness (Not Just "No Crash")

Don't just verify your code doesn't crash. Verify **OUTPUT VALUES** are correct.

**For query/filter modifications:**
```python
# BAD: Just check it runs
results = query.filter(...)  # No assertion → meaningless

# GOOD: Check result set correctness
results = query.filter(...)
assert obj_should_be_included in results, "Expected object not found"
assert obj_should_be_excluded not in results, "Unexpected object found"
assert len(results) == expected_count, f"Expected {expected_count}, got {len(results)}"
```

**For computation/formatting modifications:**
```python
# BAD: No assertion on output
formatted = format_value(input_data)

# GOOD: Check rendered output
formatted = format_value(input_data)
assert formatted == "expected_string", f"Got: {formatted}"
assert "%(placeholder)s" not in formatted, "Template not rendered"
assert abs(float(formatted) - expected_value) < 1e-10, "Numerical error"
```

**For serialization modifications:**
```python
# BAD: Only check internal state
fig2 = pickle.loads(pickle.dumps(fig))
assert fig2._original_dpi == 42  # Internal attribute

# GOOD: Check user-visible attributes
fig2 = pickle.loads(pickle.dumps(fig))
assert fig2.dpi == fig2._original_dpi, "User-visible dpi not restored"
assert fig2.get_size_inches() == fig.get_size_inches(), "Size changed"
```

---

## EXECUTION REQUIREMENTS

Before calling `finish`:

1. ✓ In your think action, explicitly state which checks apply to your patch
2. ✓ For applicable checks, provide:
   - The test code you wrote
   - The execution results
   - Whether it PASSED or FAILED
3. ✓ For non-applicable checks, explain why they don't apply
4. ✓ **ONLY call `finish` if ALL applicable checks PASS**

If any verification fails:
- Go back to fix implementation
- Revise your code
- Re-run ALL applicable verification checks
- Repeat until all checks pass

---

## WHY THIS MATTERS

Analysis of previous SWE-bench failures shows:
- **69%** of failures could have been caught by running existing tests (Check 5)
- **Round-trip bugs** (Check 1) are extremely common in I/O code
- **Differential testing** (Check 2) catches numerical correctness issues
- **Operator precedence bugs** (Check 3) are often missed by single-example testing
- **Semantic verification** (Check 6) prevents "doesn't crash but returns wrong values" bugs

This checklist catches issues **BEFORE submission**, improving resolution rate and saving iteration time.

---

**Remember:** This is a MANDATORY checklist. Do not skip any applicable checks. Your patch quality depends on thorough verification.
