"Thanks for the detailed explanation. This is Yuyang from the <> team. In the rest of the presentation, I am going to walk you through the exact benefits we gained from choosing Cloud instead of on-prem deployment. Specifically, I will cover the challenges we met during deployment and how we solved them. Also, I will discuss how the Cloud team collaborates with others to enable our Cloud users."

# **Page 5: Architecture & Security**

Firstly "Let’s talk about what PCA is and why we chose a cloud-native solution over a traditional one. **So full service naem is Aws Certificate Manager - Private Certificate Autority. It is our cloud-native 'Authentication Center.'** Its job is to sign and issue the certificates that secure every service within our firm.

**Cloud bring hightest safty out of box. PCA natively considers safety as the highest priority.** As you can see from the graph on the right, we built the PKI infrastructure using a two-layer architecture: a Root CA used to sign the Intermediate CA, and the Intermediate CA which handles the actual issuing. All CA master keys are forced to stay in an AWS-managed physical vault—a Hardware Security Module (HSM) where keys are 'burned' into the chip and **never** leave that hardware boundary. Even if someone were to physically breach the data center and steal the hardware, they would not be able to decipher the secrets. This is because the AWS hardware would detect the intrusion and **self-destruct** the keys. From the very beginning, Cloud PCA has natively met our security and regulatory requirements.

**Next is Reliability and Availability boost.** Suppose we choose onprem dployment. Then we faced data center constraints because in our current onprem setups, we have two regions - beijign and shanghai. but we only had a single AZ (Availability Zone) (you can think of them as a datacenter) per region. This meant failover had to happen at a regional level—switching traffic between Shanghai and Beijing when a disaster occurred—will typically resulted in at least a few **minutes** of downtime. By choosing AWS, we leverage **Multi-AZ redundancy**. With three independent data centers in two regions, the recovery time has been slashed from **minutes to seconds.**

**High Reliability & availability cannot be achieved by servers alone; we need make sure the data always be accessible.** This brings us to the storage of the Certificate Revocation List (CRL). There are cases where credentials are leaked or a certificate is granted to an unwanted domain, and we must be able to 'cancel' that certificate instantly. otherwise we exposed huge risk to clients and facing reputation damage risk.

That’s why we leverage **S3 Buckets**. By using S3, we gain **'11 nines' of data durability.** To put that in perspective: if you store 10 million blocked certificates, you would expect to lose only one every 10,000 years. Furthermore, S3 ensures our blacklist is **distributed** across multiple geographic data centers. It is protected by versioning and strict access contorl policies, ensuring it is effectively impossible to tamper with.

"**Last point, regarding Operational Excellence and Monitoring.** By choosing the cloud, we no longer need to deal with the overhead of **managing bare-metal DC nodes directly**. manual OS patching, hardware scaling, and managing complex backup rotations are gone. The backend servers are now fully managed by AWS and abstracted away from us; we treat the entire PCA service as a single, managed entity. 

This architectural shift allows us to manage the service as a whole through **Infrastructure as Code (IaC)**, ensuring consistency across environments. By offloading this 'heavy lifting' of infrastructure maintenance work to the cloud provider, our engineering talent is freed to focus entirely on **business logic and core security considerations**. 

To maintain total visibility, **we used CloudWatch as our 'eyes,'** CloudWatch will check real-time telemetry on our Private CA’s health. The automated alerts notify us of any certificate expiration or policy violations the moment they occur.
---

# **Page 6: The Strategy - Why Service Catalog?**

"Let's go deeper into *how* we handle IaC deployment. You might think: we have GSCloud on-prem, and we have SkyFoundry and FastTrack on Cloud, so why do we need to talk about IaC governance?

The reality is that we have chanlenegs on **'Governance Gap'** in the China environment. Years ago, when Sky China was first formed, we didn't have the Gitlab, SDLC or established guardrails; we had to start things from scratch.

While we all value **Terraform** for its flexibility, the China lacked **'Guardrails'**—the safty controls that scan and block risky terraform code before it runs. Without those brakes, using raw TF code is a massive risk for our PKI. You might mistakenly create a PCA that allows unauthorized domains, or create an S3 bucket policy that allows anyone to update the CRL blacklist. We need a solution that both flexible and safe to use.

This is when **AWS Service Catalog** comes to help, 
Service Catalog acts as our governance layer, helping us follow **'Least Privilege'** principles and making it impossible to deploy anything that doesn't meet risk requirements.

"It’s powered by **CloudFormation**. In case you’ve never heard of it, think of CloudFormation as a **'Blueprint'**—defined using either JSON or YAML—that can provisions any cloud ressouces.

"By wrapping these blueprints within **Service Catalog**, every security requirement—such as KMS encryption and strict S3 Bucket Policies—is already **'baked'** into the template. This allows us to provision fully compliant Private CAs and S3 buckets that are restricted to internal access by default. 

Users no longer need to worry about whether their policy 'writing' is secure enough, because our **Tech Risk** friends carefully helped reviewed and approved the underlying templates. For the end user, the process is seamless: they simply select the pre-approved product from the catalog, add it to their **'shopping cart,'** and check out to deploy."

The IAM team doesn't need high-level permissions to create Private CAs directly; instead, they 'order' the PCA from Sky provided products. This ensures that only **hardened secure resources** can be launched in the first place."

---

## **Part 7: Global Collaboration & Access Control**

"Lastly, let’s talk about how we empower our **PKI Team** in their deployment and maintenance. With help from our offshore peers, we localized **\<XXX\>**, which acts as the broker to map on-premise identities to cloud roles. In this way, you are granted specific cloud permissions, such as creating audit reports or issuing certificates.

**\<XXX\>** allows both **human and system accounts** to log in. In collaboration with IAM, we leverage **\<BBB\>** and **\<CCC\>** to achieve **Granular Access Control**. We can define exactly who is authorized to provision infrastructure, who can manage certificates, and who is restricted to a 'read-only' audit role.

As seen in the graph on the right, we’ve designed two distinct workflows for our onshore team and offshore peers:

* **For our Onshore Team:** The process is straightforward. Onshore users use **CI/CD pipelines** to push deployment scripts. Using the system account, they obtain temporary credentials from **\<XXX\>** to deploy resources.
* **For our Offshore Experts:** We have an additional layer required by China's regulatory framework—overseas access requires domestic approval. We partnered with the Windows Team to utilize **Lockdown Desktops**. This provides a secure, isolated environment where offshore colleagues log in, fetch a lease, and then launch the same CI/CD pipelines to manage deployments.

By localizing **\<XXX\>** and integrating it with China IAM systems, we ensure that access is strictly controlled, meeting local regulatory requirements while remaining aligned with our global design."