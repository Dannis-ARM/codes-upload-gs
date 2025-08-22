<#-- Define the command to execute -->
python my_script.py --users <#-- Loop through the list and print each item separated by a space -->
<#list users as user>
    "${user}"<#-- Add a space after each item -->
<#if user_has_next> </#if></#list>