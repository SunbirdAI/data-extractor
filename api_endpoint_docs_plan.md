## General Documentation Rules & Procedures

1. **Endpoint Description**  
   - Provide a concise yet complete description of what the endpoint does.  
   - State any relevant context (e.g., does it integrate with an external service? Does it handle certain types of data?).

2. **HTTP Method & Endpoint Path**  
   - Clearly specify the HTTP method (GET, POST, PUT, etc.).  
   - Include the path (e.g., `/process_zotero_library_items`).

3. **Parameters or Request Body**  
   - List all parameters (path/query) and/or the request body schema.  
   - Document each field in the request body model (if any), including data types, allowed values (enums), constraints, and whether they are required or optional.

4. **Request Example**  
   - Provide a JSON or cURL example of how the request should look.  
   - Show the minimal required fields as well as a more comprehensive example, if relevant.

5. **Success Response**  
   - Specify the structure of the JSON (or other format) returned upon success.  
   - Include the status code and data model (if you’re returning a Pydantic model).

6. **Error Responses**  
   - List possible error conditions (e.g., `400 Bad Request`, `404 Not Found`, `500 Internal Server Error`) and explain why they might occur.  
   - Provide a sample error message or structure.

7. **Additional Notes**  
   - Include any constraints, performance considerations, or usage tips.  
   - Document dependencies on external services or libraries, if relevant.

8. **Versioning or Tagging (if applicable)**  
   - Note the endpoint’s version if your API uses versioning.  
   - List any specific tags or relevant categories (e.g., `["zotero"]`).

---

## Applying the Rules to Each Endpoint

### 1. `/process_zotero_library_items`
1. **Endpoint Description**  
   - **Purpose**: Processes items from a Zotero library using provided Zotero credentials.
   - **Context**: Integrates with Zotero to fetch and process library items.

2. **HTTP Method & Path**  
   - **Method**: `POST`  
   - **Path**: `/process_zotero_library_items`
   - **Tags**: `["zotero"]`

3. **Parameters or Request Body**  
   - **Request Body Model**: `ZoteroCredentials`  
     - **Fields**:  
       1. `library_id` (string, required): Zotero library identifier.  
       2. `api_access_key` (string, required): Zotero API access key.
     - **Constraints**: both fields must be non-empty strings.

4. **Request Example**  
   ```json
   {
     "library_id": "1234567",
     "api_access_key": "ZoteroApiKeyXYZ"
   }
   ```

5. **Success Response**  
   ```json
   {
     "result": {
       "someProcessedData": "..."
     }
   }
   ```  
   - The exact structure of `"result"` depends on the external call to the `client.predict` method.

6. **Error Responses**  
   - `400 Bad Request`: If required fields are missing or invalid.  
   - `500 Internal Server Error`: If there is an issue calling `client.predict` or a failure in Zotero service.

7. **Additional Notes**  
   - Relies on external `client.predict()` to process Zotero library data.  
   - No file downloads or uploads here.  
   - Make sure `library_id` and `api_access_key` are correct and valid in the Zotero system.

---

### 2. `/get_study_info`
1. **Endpoint Description**  
   - **Purpose**: Retrieves detailed information about a specific study from Zotero or a related service.
   - **Context**: Integrates with a remote service to get study details based on a `study_name`.

2. **HTTP Method & Path**  
   - **Method**: `POST`  
   - **Path**: `/get_study_info`
   - **Tags**: `["zotero"]`

3. **Parameters or Request Body**  
   - **Request Body Model**: `Study`  
     - **Fields**:  
       1. `study_name` (string, required): The name of the study to fetch info for.
     - **Constraints**: non-empty string.

4. **Request Example**  
   ```json
   {
     "study_name": "Global Ebola Research"
   }
   ```

5. **Success Response**  
   ```json
   {
     "result": {
       "studyDetails": "some details here"
       // additional data
     }
   }
   ```

6. **Error Responses**  
   - `400 Bad Request`: Missing or invalid `study_name`.  
   - `500 Internal Server Error`: Issues in the external `client.predict` call.

7. **Additional Notes**  
   - This endpoint expects a valid study name that exists in the external system.  
   - Return data structure is dependent on `client.predict`.

---

### 3. `/study_variables`
1. **Endpoint Description**  
   - **Purpose**: Processes text and returns study variable data.
   - **Context**: Uses an external service to interpret a textual prompt with a specified study variable and prompt type.

2. **HTTP Method & Path**  
   - **Method**: `POST`  
   - **Path**: `/study_variables`
   - **Tags**: `["zotero"]`

3. **Parameters or Request Body**  
   - **Request Body Model**: `StudyVariableRequest`  
     - **Fields**:  
       1. `study_variable`: Enum (`Ebola Virus`, `Vaccine coverage`, `GeneXpert`) or string  
       2. `prompt_type`: Enum (`Default`, `Highlight`, `Evidence-based`)  
       3. `text`: string (non-empty)
     - **Constraints**:  
       - `text` must be at least 1 character long.  
       - `study_variable` can be one of the enumerated values or a custom string.

4. **Request Example**  
   ```json
   {
     "study_variable": "Ebola Virus",
     "prompt_type": "Default",
     "text": "Summarize the latest Ebola Virus research."
   }
   ```

5. **Success Response**  
   ```json
   {
     "result": {
       // some processed result from client.predict
     }
   }
   ```
   - Typically returns the first item of the `result` array (`result[0]` in code).

6. **Error Responses**  
   - `400 Bad Request`: Invalid or missing fields in the request body.  
   - `500 Internal Server Error`: If the external service fails or unexpected errors occur.

7. **Additional Notes**  
   - The request fields are flexible for the `study_variable` attribute.  
   - `prompt_type` restricts to an enum, so you must provide a valid type.

---

### 4. `/new_study_choices`
1. **Endpoint Description**  
   - **Purpose**: Fetches a list of new study choices or suggestions.
   - **Context**: The endpoint triggers `client.predict()` with `api_name="/new_study_choices"`. The result presumably contains recommended or newly added study options.

2. **HTTP Method & Path**  
   - **Method**: `POST`  
   - **Path**: `/new_study_choices`
   - **Tags**: `["zotero"]`

3. **Parameters or Request Body**  
   - **Request Body**: No request body is expected. This endpoint does not accept any parameters.

4. **Request Example**  
   - *Since no body is required, a POST call would be:*
   ```bash
   curl -X POST http://<host>/new_study_choices
   ```

5. **Success Response**  
   ```json
   {
     "result": [
       // array of study choices or other data from the external system
     ]
   }
   ```

6. **Error Responses**  
   - `500 Internal Server Error`: If `client.predict` fails internally.

7. **Additional Notes**  
   - This is a simple endpoint that delegates to the `client.predict` method with no additional input.  
   - The external service logic determines the actual returned data structure.

---

### 5. `/download_csv`
1. **Endpoint Description**  
   - **Purpose**: Takes headers and data, then triggers a CSV download from the server.
   - **Context**: It accepts a payload containing a DataFrame-like structure (`headers` and `data`) and returns a CSV file.

2. **HTTP Method & Path**  
   - **Method**: `POST`  
   - **Path**: `/download_csv`
   - **Tags**: `["zotero"]`

3. **Parameters or Request Body**  
   - **Request Body Model**: `DownloadCSV`  
     - **Fields**:  
       1. `headers`: List of strings.  
       2. `data`: List of lists (each sublist corresponds to a row).  
       3. `metadata`: (optional) Any type, can be `null`.
   - **Constraints**:  
     - `headers` length should match the number of columns in each row of `data`.
     - `data` is a 2D list.

4. **Request Example**  
   ```json
   {
     "headers": ["Column1", "Column2", "Column3"],
     "data": [
       ["Value1", "Value2", "Value3"],
       ["Value4", "Value5", "Value6"]
     ],
     "metadata": {
       "description": "Sample data"
     }
   }
   ```

5. **Success Response**  
   - Returns a CSV file via `FileResponse`.
   - The CSV file will be named based on the server’s file path.  
   - **Headers**: `Content-Disposition: attachment; filename=<generated_name>.csv`

6. **Error Responses**  
   - `404 Not Found`: If the generated CSV file path is invalid or file not found.  
   - `400 Bad Request`: If `headers` or `data` are malformed (not strictly enforced in code, but good to note).  
   - `500 Internal Server Error`: If saving, retrieving, or cleaning up the file fails.

7. **Additional Notes**  
   - This endpoint calls `client.predict` to convert the given data into CSV.  
   - Post-download, it calls `client.predict(api_name="/cleanup_temp_files")` to remove temporary files.  
   - If your system has large CSVs, consider memory constraints or streaming approaches.

---

### 6. `/upload_and_process_pdf_files`
1. **Endpoint Description**  
   - **Purpose**: Upload multiple PDF files for a given study, process them, and return structured data (in a DataFrame-like JSON format).
   - **Context**: Saves uploaded files to disk, processes them to extract relevant study variables, and then returns a structured JSON representation of the results. Also writes a CSV to disk for the specified `study_name`.

2. **HTTP Method & Path**  
   - **Method**: `POST`  
   - **Path**: `/upload_and_process_pdf_files`
   - **Tags**: `["zotero"]`

3. **Parameters or Request Body**  
   - **Form Fields**:  
     1. `study_name` (string, required): The name of the study to associate with these PDFs.  
     2. `study_variables` (string, required): A string representing the study variables.  
   - **Files**:  
     - `files`: A list of PDF files uploaded via multipart/form-data.
   - **Constraints**:  
     - `study_name` cannot be empty.  
     - `study_variables` cannot be empty.  
     - `files` should be valid PDFs or at least valid file objects to be processed.

4. **Request Example (cURL)**  
   ```bash
   curl -X POST http://<host>/upload_and_process_pdf_files \
        -F "study_name=EbolaStudy2025" \
        -F "study_variables=Ebola Virus, Transmission" \
        -F "files=@/path/to/file1.pdf" \
        -F "files=@/path/to/file2.pdf"
   ```

5. **Success Response**  
   - Returns JSON containing `data`, `headers`, and `metadata`. Example:
   ```json
   {
     "data": {
       "headers": ["Column1", "Column2"],
       "data": [
         ["val1", "val2"],
         ["val3", "val4"]
       ],
       "metadata": {
         "dtypes": ["object", "object"],
         "index": [0, 1],
         "null_counts": [0, 0],
         "shape": [2, 2]
       }
     }
   }
   ```

6. **Error Responses**  
   - `400 Bad Request`: Missing or invalid form fields.  
   - `500 Internal Server Error`:  
     - If file saving fails.  
     - If the PDF processing fails.  
     - If CSV export fails.

7. **Additional Notes**  
   - The endpoint saves PDFs to `UPLOAD_DIR`, processes them, updates the DataFrame, and exports to a CSV in `zotero_data/<study_name>.csv`.  
   - Temporary files are cleaned up via `client.predict(api_name="/cleanup_temp_files")`.  
   - The final response is a structured data representation from the processed PDFs.

---
