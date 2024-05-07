# ==============================================================================
# Mandatory variables

variable "bucket_name" { description = "The S3 bucket name" }

# ==============================================================================
# Default variables

variable "attach_policy" { default = false }
variable "policy" { default = null }
variable "lifecycle_rule_inputs" { default = [] }

variable "force_destroy" {
  description = "Whether to forcefully destroy the bucket when it contains objects"
  type        = bool
  default     = false
}

variable "target_access_logging_bucket" {
  description = "The name of the bucket where S3 to store server access logs"
  default     = null
}

variable "target_access_logging_prefix" {
  description = "A prefix for all log object keys"
  default     = null
}

variable "block_public_acls" {
  description = "Whether to block public ACLs"
  type        = bool
  default     = true
}

variable "block_public_policy" {
  description = "Whether to block public bucket policies"
  type        = bool
  default     = true
}

variable "ignore_public_acls" {
  description = "Whether to ignore public ACLs"
  type        = bool
  default     = true
}

variable "restrict_public_buckets" {
  description = "Whether to restrict public and cross-account access if bucket has public policies or ACLs"
  type        = bool
  default     = true
}
variable "website_map" {
  description = "Map containing static website hosting"
  default     = {}
}
