# Pre-submission Verification Checklist
# (To be injected into Agent System Prompt)

---

## MANDATORY: Verify Before Calling `finish`

Before you call the `finish` tool to submit your patch, you **MUST** complete the following verification checks. Answer each applicable item in your think action.

---

### ✓ Check 1: I/O Round-trip Testing

**IF your patch modifies:**
- File read/write operations
- Serialization/deserialization
- Format/parse functions
- Data encoding/decoding

**THEN you MUST verify:**

```python
# Pattern 1: write → read consistency
original_data = create_test_data()
write_function(original_data, "/tmp/test_file")
read_back = read_function("/tmp/test_file")
assert read_back == original_data, "Write-read mismatch!"

# Pattern 2: format → parse consistency
original_obj = create_test_object()
formatted_str = format_function(original_obj)
parsed_obj = parse_function(formatted_str)
assert parsed_obj == original_obj, "Format-parse mismatch!"
```

**CRITICAL:**
- If you modified **write logic**, did you also test that **read logic** correctly reads it back?
- If you modified **format logic**, did you also test that **parse logic** correctly parses it?
- Testing only one direction (write OR read) is **INSUFFICIENT**

**Example:** If you fixed a bug in table.write(), you MUST also verify table.read() works correctly with the new format.

---

### ✓ Check 2: Differential Testing (for numerical/computational code)

**IF your patch modifies:**
- Mathematical calculations
- Numerical algorithms
- Data transformations

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

**If no reference exists, at minimum verify:**
- Hand-calculated expected outputs for known inputs
- Mathematical properties (e.g., idempotency: f(f(x)) == f(x))

---

### ✓ Check 3: Operator Precedence and Expression Correctness

**IF your patch modifies:**
- Operator overloading (`__add__`, `__sub__`, `__or__`, `__and__`, etc.)
- Expression evaluation
- Set/bitwise/arithmetic operations

**THEN you MUST verify operator precedence:**

```python
# Example: (A - B) | C  vs  A - (B | C)
# These give DIFFERENT results!

# Create test cases where precedence matters:
A = {1, 2, 3, 4}
B = {2, 3}
C = {3, 4, 5}

# If you meant (A - B) | C:
expected = {1, 4} | {3, 4, 5}  # = {1, 3, 4, 5}

# Make sure your code doesn't accidentally do A - (B | C):
wrong = {1, 2, 3, 4} - ({2, 3} | {3, 4, 5})  # Different result!

result = your_expression_with_A_B_C()
assert result == expected, f"Operator precedence error: {result} != {expected}"
```

**KEY:** Don't just test with the MVCE example. Create test cases with **non-empty intersections** to trigger precedence bugs.

---

### ✓ Check 4: Boundary and Special Value Testing

**For each input parameter your code handles, test:**

| Parameter Type | Required Boundary Values |
|---------------|-------------------------|
| Strings | `""` empty, `" "` whitespace, very long strings |
| Numbers | `0`, `-1`, negative values, `NaN`, `Infinity` |
| Collections | `[]` empty, single element, overlapping sets |
| Paths | `path`, `./path`, `../x/path`, absolute paths |
| Objects | `None`, subclass instances, edge cases |

---

### ✓ Check 5: Regression Testing (Run Existing Tests)

**Before submitting, run the existing test suite for the module you modified:**

```bash
# 1. Before modifying code, record baseline
python -m pytest tests/relevant_module/ -v --tb=no > /tmp/baseline.txt 2>&1

# 2. Apply your modifications

# 3. Run the same tests again
python -m pytest tests/relevant_module/ -v --tb=short > /tmp/modified.txt 2>&1

# 4. Check for regressions
diff <(grep "PASSED" /tmp/baseline.txt | sort) \
     <(grep "PASSED" /tmp/modified.txt | sort)
```

**If any previously-passing test now fails, you MUST fix the regression before submitting.**

---

### ✓ Check 6: Semantic Correctness (Not Just "No Crash")

Don't just verify your code doesn't crash. Verify the **output values** are correct:

**For query modifications:**
```python
# BAD: Just check it runs
results = query.filter(...)  # No assertion → meaningless

# GOOD: Check result set correctness
results = query.filter(...)
assert obj_should_be_included in results
assert obj_should_be_excluded not in results
```

**For computation modifications:**
```python
# BAD: No assertion
formatted = format_value(input)

# GOOD: Check rendered output
formatted = format_value(input)
assert formatted == "expected_string"
assert "%(placeholder)s" not in formatted  # Check template rendered
```

---

## Execution Requirements

Before calling `finish`:

1. ✓ In your think action, confirm which checks apply to your patch
2. ✓ For applicable checks, provide your test code and results
3. ✓ For non-applicable checks, explain why they don't apply
4. ✓ **Only call `finish` if ALL applicable checks PASS**

If any verification fails, go back to modify your code, then re-verify.

---

## Why This Matters

Based on analysis of previous failures:
- **69% of failures** could have been caught by running existing tests (Check 5)
- **Round-trip bugs** (Checks 1) are extremely common in I/O code
- **Differential testing** (Check 2) catches numerical correctness issues
- **Operator precedence** (Check 3) bugs are often missed by single-example testing
- **Semantic verification** (Check 6) prevents "doesn't crash but returns wrong values" bugs

This checklist is designed to catch issues **before you submit**, saving iteration time and improving resolution rate.
