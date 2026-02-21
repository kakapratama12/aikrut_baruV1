# Job Analysis 400 Error - Diagnostic Information

## Current Status

### ✅ Confirmed Working:
1. API Key IS saved in database:
   ```json
   {
     "type": "global",
     "model_name": "openai/gpt-4o-mini", 
     "openrouter_api_key": "sk-or-v1-6b15bba8dc...fe54e" (80 chars)
   }
   ```

2. Other AI operations working (company values, job description, playbook)

3. Analysis endpoint updated to use `get_global_ai_settings()`

### ❌ Still Failing:
- Job Analysis returns: "400: OpenRouter API key not configured"

### 🔍 Debugging Steps Added:

1. **In `get_global_ai_settings()`:**
   - Logs when settings are retrieved
   - Logs whether API key exists
   - Logs API key length
   - Logs model name

2. **In `run_batch_analysis()`:**
   - Logs after retrieving global settings
   - Shows has_key status

3. **In `call_openrouter_with_usage()`:**
   - Logs when function is called
   - Shows has_key status, key length, model

### 🎯 What to Check:

**When you run job analysis, the logs should show:**
```
INFO - Global AI settings retrieved - has API key: True, key_length: 80, model: openai/gpt-4o-mini
INFO - Analysis: Retrieved global settings - has_key: True, model: openai/gpt-4o-mini  
INFO - call_openrouter_with_usage called - has_key: True, key_length: 80, model: openai/gpt-4o-mini
```

**If you see:**
- `has API key: False` → Settings not being retrieved from DB
- `key_length: 0` → API key is empty string in DB
- No logs at all → Analysis endpoint not being called

### 📝 Next Steps:

1. Try job analysis now
2. Check logs: `tail -n 100 /var/log/supervisor/backend.err.log | grep -E "Analysis|global|call_openrouter"`
3. Share what error you see in the UI
4. Share what logs show

This will help us pinpoint exactly where the API key is getting lost.
