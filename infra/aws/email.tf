resource "aws_ses_domain_identity" "main" {
  provider = aws.ses
  domain   = local.mail_domain
}

resource "aws_route53_record" "ses_verification" {
  zone_id = var.hosted_zone_id
  name    = "_amazonses.${local.mail_domain}"
  type    = "TXT"
  ttl     = 300
  records = [aws_ses_domain_identity.main.verification_token]
}

resource "aws_ses_domain_identity_verification" "main" {
  provider   = aws.ses
  domain     = aws_ses_domain_identity.main.id
  depends_on = [aws_route53_record.ses_verification]
}

data "aws_caller_identity" "ses" {
  provider = aws.ses
}

data "aws_iam_policy_document" "ses_events_kms" {
  statement {
    sid       = "EnableAccountAdministration"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.ses.account_id}:root"]
    }
  }

  statement {
    sid = "AllowSesAndSnsEnvelopeEncryption"
    actions = [
      "kms:Decrypt",
      "kms:GenerateDataKey*",
    ]
    resources = ["*"]

    principals {
      type        = "Service"
      identifiers = ["ses.amazonaws.com", "sns.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceAccount"
      values   = [data.aws_caller_identity.ses.account_id]
    }
  }
}

resource "aws_kms_key" "ses_events" {
  provider                = aws.ses
  description             = "VIP ${var.environment} SES event notifications"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.ses_events_kms.json
}

resource "aws_sns_topic" "ses_events" {
  provider          = aws.ses
  name              = "${local.name}-ses-events"
  kms_master_key_id = aws_kms_key.ses_events.arn
}

data "aws_iam_policy_document" "ses_events" {
  statement {
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.ses_events.arn]

    principals {
      type        = "Service"
      identifiers = ["ses.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceAccount"
      values   = [data.aws_caller_identity.ses.account_id]
    }
  }
}

resource "aws_sns_topic_policy" "ses_events" {
  provider = aws.ses
  arn      = aws_sns_topic.ses_events.arn
  policy   = data.aws_iam_policy_document.ses_events.json
}

resource "aws_sns_topic_subscription" "ses_events_email" {
  provider  = aws.ses
  topic_arn = aws_sns_topic.ses_events.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_ses_identity_notification_topic" "events" {
  for_each = toset(["Bounce", "Complaint", "Delivery"])

  provider                 = aws.ses
  topic_arn                = aws_sns_topic.ses_events.arn
  notification_type        = each.value
  identity                 = aws_ses_domain_identity.main.domain
  include_original_headers = false

  depends_on = [aws_sns_topic_policy.ses_events]
}

resource "aws_ses_domain_dkim" "main" {
  provider = aws.ses
  domain   = aws_ses_domain_identity.main.domain
}

resource "aws_route53_record" "ses_dkim" {
  count = 3

  zone_id = var.hosted_zone_id
  name    = "${aws_ses_domain_dkim.main.dkim_tokens[count.index]}._domainkey.${local.mail_domain}"
  type    = "CNAME"
  ttl     = 300
  records = ["${aws_ses_domain_dkim.main.dkim_tokens[count.index]}.dkim.amazonses.com"]
}

resource "aws_ses_domain_mail_from" "main" {
  provider         = aws.ses
  domain           = aws_ses_domain_identity.main.domain
  mail_from_domain = "bounce.${local.mail_domain}"
}

resource "aws_route53_record" "ses_mail_from_mx" {
  zone_id = var.hosted_zone_id
  name    = aws_ses_domain_mail_from.main.mail_from_domain
  type    = "MX"
  ttl     = 300
  records = ["10 feedback-smtp.${var.ses_region}.amazonses.com"]
}

resource "aws_route53_record" "ses_mail_from_spf" {
  zone_id = var.hosted_zone_id
  name    = aws_ses_domain_mail_from.main.mail_from_domain
  type    = "TXT"
  ttl     = 300
  records = ["v=spf1 include:amazonses.com -all"]
}

resource "aws_route53_record" "dmarc" {
  zone_id = var.hosted_zone_id
  name    = "_dmarc.${local.mail_domain}"
  type    = "TXT"
  ttl     = 300
  records = ["v=DMARC1; p=quarantine; rua=mailto:dmarc@${var.root_domain}; adkim=s; aspf=s; pct=100"]
}
