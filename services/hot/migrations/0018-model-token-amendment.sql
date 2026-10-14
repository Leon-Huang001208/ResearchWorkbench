ALTER TABLE hot.model_control_requests DROP CONSTRAINT model_control_requests_operation_check;
ALTER TABLE hot.model_control_requests ADD CONSTRAINT model_control_requests_operation_check
CHECK(operation IN ('authorize','terminate','amend-tokens'));
