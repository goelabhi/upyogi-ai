
import streamlit as st
from backend import (
    submit_grievance,
    save_image_grievance,
    get_all_grievances,
    update_status,
    get_officer_intelligence
)

st.set_page_config(
    page_title="upyogi.ai",
    page_icon="🏛️",
    layout="wide"
)

st.title("🏛️ upyogi.ai")
st.caption("AI-powered grievance intelligence")

role = st.sidebar.radio(
    "Select portal",
    ["Citizen", "Officer"]
)


# =========================
# CITIZEN
# =========================

if role == "Citizen":

    st.header("Report a Grievance")

    st.subheader("Citizen Information")

    citizen_name = st.text_input(
        "Name",
        placeholder="Enter your full name"
    )

    mobile_number = st.text_input(
        "Mobile Number",
        placeholder="Enter your mobile number"
    )

    citizen_address = st.text_area(
        "Address",
        placeholder="Enter your residential address"
    )

    st.subheader("Grievance")

    location = st.text_input(
        "Where is the problem?",
        placeholder="Example: Mathura, Uttar Pradesh"
    )

    complaint = st.text_area(
        "Describe your problem",
        placeholder="Example: There has been no drinking water in my village for three days..."
    )

    uploaded_image = st.file_uploader(
        "Or upload a photo of the grievance",
        type=["jpg", "jpeg", "png"]
    )

    if st.button("Submit Grievance", type="primary"):
    
        if not complaint.strip() and uploaded_image is None:
            st.warning("Please describe your grievance or upload a photo.")
    
        elif uploaded_image is not None:
    
            image_bytes = uploaded_image.getvalue()
    
            result = save_image_grievance(
            image_bytes,
            citizen_name,
            mobile_number,
            citizen_address,
            location
    )
    
            st.success("Grievance submitted successfully.")
    
            st.write("### Grievance Details")
            st.write("**Category:**", result["category"])
            st.write("**Location:**", result["location"])
            st.write("**Urgency:**", result["urgency"])
            st.write("**Department:**", result["department"])
            st.write("**Summary:**", result["summary"])
    
        else:
    
            result = submit_grievance(
                 complaint,
                 citizen_name,
                 mobile_number,
                 citizen_address,
                 location
             )
    
            st.success("Grievance submitted successfully.")
    
            st.write("### Grievance Details")
            st.write("**Category:**", result["category"])
            st.write("**Location:**", result["location"])
            st.write("**Urgency:**", result["urgency"])
            st.write("**Department:**", result["department"])
            st.write("**Summary:**", result["summary"])

# =========================
# OFFICER
# =========================

else:

    st.header("Officer Dashboard")

    intelligence = get_officer_intelligence()
    grievances = get_all_grievances()

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total Grievances",
        intelligence["total_grievances"]
    )

    col2.metric(
        "New Grievances",
        intelligence["new_grievances"]
    )

    col3.metric(
        "Systemic Issues",
        len(intelligence["systemic_issues"])
    )

    st.divider()

    st.subheader("🚨 Systemic Issues")

    if intelligence["systemic_issues"]:

        for issue in intelligence["systemic_issues"]:

            st.warning(
                f"{issue['priority']} Priority — "
                f"{issue['location']} — "
                f"{issue['category']}"
            )

            st.write(
                f"Related grievances: {issue['grievance_ids']}"
            )

            #st.write(
             #   f"Relatedness score: "
              #  f"{issue['relatedness_score']}"
            #)

            st.write("**Evidence:**")

            for evidence in issue["evidence"]:
                st.write(f"• {evidence}")
            
            st.write(
                "**Recommended action:**",
                issue["recommended_action"]
            )

    else:
        st.info("No systemic issues detected.")

    st.divider()

    st.subheader("All Grievances")

    for grievance in grievances:

        (
            grievance_id,
            complaint,
            category,
            location,
            urgency,
            department,
            summary,
            status,
            created_at,
            citizen_name,
            mobile_number,
            citizen_address
        ) = grievance

        with st.expander(
            f"#{grievance_id} — {category} — {location}"
        ):

            st.write("**Complaint:**", complaint)
            st.write("**Summary:**", summary)
            st.write("**Urgency:**", urgency)
            st.write("**Department:**", department)
            st.write("**Status:**", status)
            st.write("**Created:**", created_at)

            new_status = st.selectbox(
                "Update status",
                [
                    "New",
                    "Assigned",
                    "In Progress",
                    "Resolved"
                ],
                index=[
                    "New",
                    "Assigned",
                    "In Progress",
                    "Resolved"
                ].index(status),
                key=f"status_{grievance_id}"
            )

            if st.button(
                "Update",
                key=f"update_{grievance_id}"
            ):

                update_status(
                    grievance_id,
                    new_status
                )

                st.success("Status updated.")
                st.rerun()
