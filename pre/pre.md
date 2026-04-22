# **Page 5:**

"Let’s talk about what PCA is and why we chose a cloud-native solution over a traditional one. **AWS Private CA is our cloud-native 'Authentication Center.'** Its job is to sign and issue the digital IDs that secure every service within our firm.

Regarding the benefits of the cloud, **first is Security and Private Master Key Storage.** We achieve the same high-level security standards as an on-prem HashiCorp Vault setup, but natively. AWS PCA forces master keys into a **'Physical Vault'**—a Hardware Security Module where keys are 'burned' into the chip and **never** leave that hardware boundary. Even if someone were to physically breach the data center and steal the hardware, the HSM would detect it and **self-destruct** the keys. "From the very beginning, Cloud PCA has natively met our security and compliance requirements."

**Next is Reliability and Availability.** In our traditional on-prem environment in China, we faced data center constraints where we only have a single AZ per region. This means failover must happen at a regional level—switching traffic between Shanghai and Beijing—which typically takes **minutes** of downtime. By chosing the cloud, we leverage **Multi-AZ redundancy**. With three independent data centers in each region and PCA’s native auto-failover, we slash recovery time from **minutes down to serveral seconds.**

**But high availability isn't just for the servers; it’s critical for our data as well.** This brings us to the **CRL**, or **Certificate Revocation List**. Think of the CRL as an **'Blacklist.'** Issuing an ID is only half the battle; if a credential is leaked or the certifcat is created on an unwanted domain, we must be able to 'cancel' that ID instantly. 

That’s why we leverage **AWS S3 Bucket** for our CRL storage. By using an S3-backed CRL, we gain **'11 nines' of durability.** To put that in perspective: if you store 10 million CRL records, you would expect to lose only one every 10,000 years. Furthermore, S3 ensures our blacklist is **physically distributed** across multiple geographic locations. It is protected by versioning and strict access policies, ensuring that our 'Blacklist' is effectively impossible to tamper with.

"**Finally, from a Monitoring and Operational perspective.** We are transitioning from the overhead of **'managing bare-metal machines'—patching OS, scaling hardware, and manual backups—to simply 'calling an API.'** AWS Private CA is essentially a **'set-and-forget'** solution. We use cloud-native IaC for deployment, and CloudWatch acts as our **'automated eyes'** to track issuance rates and CRL health in real-time. By offloading the infrastructure layer to the cloud, we’ve built an automated PKI that requires **minimal maintenance work.**"

---

# **Page 6: The Strategy - Why Service Catalog?**
"To achieve operational excellence, we had to bridge a practical **'Governance Gap'** in our local environment. While we all value **Terraform** for its flexibility, we currently lack the automated **'Guardrails'**—the real-time safety nets that scan and block non-compliant code before it runs. Without those brakes, using raw IaC is a massive risk for our PKI. We needed a solution that was **'Secure by Default.'**

"This is why we chose **AWS Service Catalog**, powered by **CloudFormation**. Think of CloudFormation as our cloud-native **'Architecture Blueprint.'** By wrapping it in Service Catalog, we’ve moved from handing out raw parts to providing a **'Pre-approved Product.'** Every security requirement—like KMS encryption and strict Bucket Policies—is already 'baked' into the template. You no longer need to worry about 'writing' the security yourself because our friends in Tech Risk have already reviewed and approved the logic; you simply choose the product from the shopping cart and deploy. Because it’s powered by CloudFormation, we get robust **version control, automatic rollbacks, and built-in dependency management** out-of-the-box. If a deployment fails, the system handles the cleanup automatically, ensuring the environment stays clean and stable.

Service Catalog acts as our governance layer, making it impossible to deploy anything that doesn't meet Tech Risk requirements. The real achievement here is that we’ve implemented **Shift-Left Governance** without needing complex Terraform or CDK guardrails. 

With Service Catalog, we achieve **'Least Privilege'** at scale. Developers don't need high-level permissions to create sensitive resources like Private CAs; they only need permission to 'order' from our secure shopping list. This ensures that only **authorized, hardened architectures** can be launched in the first place."



## **Part 7: Global Collaboration & Access Control**

"Lastly, let’s talk about how we empower our **PKI Team**. We’ve integrated AWS PCA with our **Corporate Identity System**, meaning the team logs in using their **standard corporate accounts**. This allows for **Granular Access Control**: we define exactly who can provision infrastructure versus who is strictly limited to auditing logs.

To make this work globally while staying compliant, we’ve designed two workflows:

* **For our Onshore Team:** They use our local **GitLab CI/CD pipelines** to obtain temporary credentials via China indentity providers and deploy resources directly.
* **For our Offshore Experts:** We want to leverage global expertise without 'reinventing the wheel.' Due to local regulatory requirements, overseas access requires additional domestic approval. We partnered with the Windows Team to utilize **Lock-down Desktops**. This provides a secure, isolated environment where offshore colleagues—once their lease is approved—can use the same China GitLab pipelines to manage deployments.

By integrating with our internal identity providers, we’ve created a centralized, secure environment. Authentication and authorization are handled automatically, ensuring that only the right people have the **'keys to the kingdom'** at all times."


