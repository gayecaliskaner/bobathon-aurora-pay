provider "aws" {
  region = "eu-central-1"
}

variable "db_password" {
  type      = string
  sensitive = true
}

resource "aws_security_group" "core_api" {
  name        = "aurora-core-api"
  description = "Aurora Core API"

  ingress {
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }
}

resource "aws_s3_bucket" "statements" {
  bucket = "aurora-customer-statements"
  acl    = "private"
}

resource "aws_db_instance" "core" {
  identifier          = "aurora-core-db"
  engine              = "postgres"
  instance_class      = "db.t3.medium"
  allocated_storage   = 50
  username            = "aurora"
  password            = var.db_password
  storage_encrypted   = true
  publicly_accessible = false
  skip_final_snapshot = true
}
